import os
import signal
import argparse
import subprocess
import time
import csv
import logging
import re
import threading
import json

from collections import deque
from subprocess import Popen, PIPE
from datetime import datetime

from cmd_utils import cmd_iw_dev, cmd_ip_link_set, cmd_ip_link_show
from scanner import Scanner

log = logging.getLogger('logger')


def main(args):
    """
    This program monitors the signal strength of the connected wifi access point (AP).
    When the signal is lost the program activates OLSR on the wifi interface.
    While OLSR is activated the program continuously scans for the APs SSID to reappear in range.
    When the APs SSID is again in range the program deactivates OLSR and reconnects to the AP.
    """
    if args.scaninterface:
        scaninterface = args.scaninterface
    else:
        scaninterface = args.interface
    path = os.path.dirname(os.path.abspath(__file__))
    statistics_dir = path + '/data/statistics/' + args.outputpath + '/'
    if not os.path.isdir(statistics_dir):
        os.makedirs(statistics_dir)
    if args.qdisc > 0:
        rate, unit = 1, 'mbit'
        print("*** Setting up qdisc with HTB rate {} {}".format(rate, unit))
        init_qdisc(args.interface, rate, unit)
        log.info("*** {}: Qdisc set up with HTB rate {} {}".format(args.interface, rate, unit))
        # print(subprocess.Popen("tc -g -s class show dev " + args.interface, stdout=PIPE, stderr=PIPE, shell=True).communicate())
        qdisc = 'on'
        qdisc_throttle = str(args.qdisc) + 'bit'
    else:
        qdisc = 'off'
        qdisc_throttle = None
    if args.noolsr:
        olsr = 'off'
    else:
        olsr = 'on'
    parameters = {'start_time': args.starttime, 'OLSR': olsr, 'interface': args.interface,
                  'qdisc': {'mode': qdisc, 'throttle': qdisc_throttle},
                  'AP': {'ssid': args.apssid, 'bssid': args.apbssid, 'ip': args.apip},
                  'scan': {'interface': scaninterface, 'interval': args.scaninterval,
                           'moving_avg_window': args.signalwindow,
                           'reconnect_threshold': args.reconnectthreshold,
                           'disconnect_threshold': args.disconnectthreshold}}
    with open(statistics_dir + 'start_params.json', 'w') as file:
        json.dump(parameters, file, indent=4)
    flexible_sdn_olsr(args.interface, scaninterface, args.scaninterval, args.reconnectthreshold, args.disconnectthreshold, args.pingto,
                      statistics_dir, args.apssid, args.apbssid, args.apip, args.signalwindow, args.starttime, args.qdisc, args.noolsr)


def flexible_sdn_olsr(interface: str, scaninterface: str, scan_interval: float, reconnect_threshold: float, disconnect_threshold: float,
                      pingto: str, out_path: str, ap_ssid: str, ap_bssid: str, ap_ip: str, signal_window: int, start_time: float, qdisc: int, no_olsr: bool = False):
    """
    This function monitors the wifi signal strength as long there is a connection to the AP.
    When the connection is lost it starts the OLSR and continuously scans for the AP to reappear.
    When the AP reappears OLSR is deactivated and a connection to the AP will be established.
    """
    log.info("*** {}: Interface: {}, Scan-interface: {}".format(interface.split('-')[0], interface, scaninterface))
    station = interface.split('-')[0]
    scanner = Scanner(scaninterface, scan_interval, out_path, station, start_time, ap_ssid)
    olsrd_pid = 0
    link_signal_deque = deque(maxlen=signal_window)
    scan_signal_deque = deque(maxlen=signal_window)
    file = out_path + interface + '_signal.csv'
    stdout, stderr = cmd_iw_dev(interface, "link")
    while b'Not connected.' in stdout and b'Connected to ' + ap_bssid.encode() not in stdout:
        stdout, stderr = cmd_iw_dev(interface, "link")
    stdout, stderr = Popen(["ping", "-c1", ap_ip], stdout=PIPE, stderr=PIPE).communicate()
    if pingto:
        Popen(["ping", "-c1", pingto]).communicate()
    print("ssid, time (s), signal (dBm), signal_avg (dBm)")
    while True:
        time.sleep(1)
        ap_link_signal = get_link_signal_quality(interface, ap_bssid, ap_ssid, start_time)
        if ap_link_signal:
            signal = float(ap_link_signal['signal'].rstrip(' dBm'))
            link_signal_deque.append(signal)
            ap_link_signal.update({'signal': signal, 'signal_avg': sum(link_signal_deque) / len(link_signal_deque)})
            if ap_link_signal['signal_avg'] >= disconnect_threshold:
                print("{}, {}, {}, {:.2f}".format(ap_link_signal['SSID'], ap_link_signal['time'], ap_link_signal['signal'], ap_link_signal['signal_avg']))
                write_signal_to_file(ap_link_signal, file)
                continue
        if not scanner.is_alive():
            if ap_link_signal:
                print("*** AP signal too weak (last signal: {} / {})".format(ap_link_signal['signal'], disconnect_threshold))
            else:
                print("*** AP connection lost")
            print("*** Starting background scan")
            scanner.start()
            log_event('scanner_start', 1, start_time, out_path, station)
        scan_signal = get_scan_dump_signal(scaninterface, ap_bssid, ap_ssid, start_time)
        if scan_signal and 'signal' in scan_signal:
            scan_signal_deque.append(scan_signal['signal'])
            scan_signal.update({'signal_avg': sum(scan_signal_deque) / len(scan_signal_deque)})
            print("*** {}: Scan detected {} in range (signal: {} / {})".format(scaninterface, ap_ssid, scan_signal['signal'],
                                                                               reconnect_threshold))
            log.info("*** {}: Scan detected {} in range (signal: {} / {})".format(scaninterface, ap_ssid, scan_signal['signal'],
                                                                                  reconnect_threshold))
            write_signal_to_file(scan_signal, file)
            print("{}, {}, {}, {:.2f}".format(scan_signal['SSID'], scan_signal['time'], scan_signal['signal'],
                                              scan_signal['signal_avg']))
            if scan_signal['signal'] >= reconnect_threshold:
                log_event('reconnect', 1, start_time, out_path, station)
                olsrd_pid = reconnect_to_access_point(interface, olsrd_pid, ssid=ap_ssid, qdisc_rate=qdisc, qdisc_unit='bit')
                log_event('reconnect', 2, start_time, out_path, station)
                if scanner.is_alive():
                    print("*** Stopping background scan")
                    scanner.terminate()
                    log_event('scanner_stop', 1, start_time, out_path, station)
                    scanner = Scanner(scaninterface, scan_interval, out_path, station, start_time, ap_ssid)
                time.sleep(0.5)
                print("*** Reconnected to AP.")
                print("*** OLSRd PID: ", olsrd_pid)
                stdout, stderr = Popen(["ping", "-c1", ap_ip], stdout=PIPE, stderr=PIPE).communicate()
                continue
        if olsrd_pid == 0 and not no_olsr:
            print("*** Starting OLSRd")
            log_event('disconnect', 1, start_time, out_path, station)
            olsrd_pid = switch_to_olsr(interface, qdisc_rate=qdisc, qdisc_unit='bit')
            log_event('disconnect', 2, start_time, out_path, station)
            if pingto:
                spthread = threading.Thread(target=sleep_and_ping, kwargs={'sleep_interval': 1.0, 'ip': pingto},
                                            daemon=True)
                spthread.start()


def get_link_signal_quality(interface: str, bssid: str, ssid: str, start_time: float):
    """
    Fetches the signal strength on a given wifi interface as long as it is connected to an AP with a matching ssid.
    Returns the signal data if the connection is present.
    Returns None if the AP is not connected.
    """
    stdout, stderr = cmd_iw_dev(interface, "link")
    data = stdout.decode()
    if 'Connected to ' + bssid in data and 'SSID: ' + ssid in data:
        data = [x for x in list(filter(None, data.split('\n\t')[1:])) if x.strip()]
        data = dict(map(lambda s: s.split(':'), data))
        signal_data = {k.replace(' ', '_'): (data[k].strip() if k in data else 'NaN') for k in ['SSID', 'signal',
                                                                                                'rx bitrate',
                                                                                                'tx bitrate']}
        signal_data.update({'time': datetime.now().timestamp() - start_time})
        return signal_data
    return None


def get_scan_dump_signal(interface: str, bssid: str, ssid: str, start_time: float):
    stdout, stderr = cmd_iw_dev(interface, "scan", "dump")
    scan_data = stdout.decode()
    if "BSS " + bssid in scan_data and "SSID: " + ssid in scan_data:
        scan_signal = signal_strength_from_scan_dump(scan_data, bssid, ssid)
        scan_data = {'time': datetime.now().timestamp() - start_time, 'signal': scan_signal, 'SSID': ssid,
                     'rx_bitrate': 0, 'tx_bitrate': 0}
        return scan_data
    return None


def signal_strength_from_scan_dump(data: str, bssid: str, ssid: str):
    for d in data.split('BSS '):
        signal = extract_signal_strength(d, bssid, ssid)
        if signal:
            return signal
    return None


def extract_signal_strength(data: str, bssid: str, ssid: str):
    if data.startswith(bssid) and 'SSID: ' + ssid in data:
        entry = list(filter(None, data.split('\n\t')[1:]))
        entry = dict(map(lambda x: (x.split(':', 1) + [''])[:2], entry))
        signal = entry['signal'].strip()
        signal = re.findall(r"[-+]?\d+\.\d*|[-+]?\d+|[-+]?\.\d+", signal)
        if signal:
            return float(signal[0])
    return None


def switch_to_olsr(interface: str, qdisc_rate: int, qdisc_unit: str):
    """
    Configures the given wifi interface for OLSR and starts OLSRd in the background.
    Returns the PID of the OLSRd process.
    """
    if qdisc_rate > 0:
        rate, unit = qdisc_rate, qdisc_unit
        print("*** Updating qdisc with HTB rate {} {}".format(rate, unit))
        update_qdisc(interface, rate, unit)
        log.info("*** {}: Qdisc updated with HTB rate {} {}".format(args.interface, rate, unit))
    prepare_olsrd(interface)
    stdout = start_olsrd(interface)
    if stdout:
        olsrd_pid = int(stdout.split()[0])
        log.info("*** {}: Started olsrd in the background (PID: )".format(interface, olsrd_pid))
        print("*** OLSRd running (PID: {})".format(olsrd_pid))
        if qdisc_rate > 0:
            rate, unit = 1, 'mbit'
            print("*** Updating qdisc with HTB rate {} {}".format(rate, unit))
            update_qdisc(interface, rate, unit)
            log.info("*** {}: Qdisc updated with HTB rate {} {}".format(args.interface, rate, unit))
        return olsrd_pid
    if qdisc_rate > 0:
        rate, unit = 1, 'mbit'
        print("*** Updating qdisc with HTB rate {} {}".format(rate, unit))
        update_qdisc(interface, rate, unit)
        log.info("*** {}: Qdisc updated with HTB rate {} {}".format(args.interface, rate, unit))
    return 1


def prepare_olsrd(interface: str):
    """
    Configures the given interface for ad-hoc mode and joins IBSS.
    """
    ibss = {'ssid': 'adhocNet', 'freq': '2432', 'ht_cap': 'HT40+', 'bssid': '02:CA:FF:EE:BA:01'}
    stdout, stderr = cmd_iw_dev(interface, "set", "type", "ibss")
    log.info("*** {}: Set type to ibss".format(interface))
    stdout, stderr = cmd_ip_link_set(interface, "up")
    log.info("*** {}: Set ip link up".format(interface))
    stdout, stderr = cmd_iw_dev(interface, "ibss", "join", ibss['ssid'], ibss['freq'], ibss['ht_cap'], ibss['bssid'])
    log.info("*** {}: Join ibss adhocNet".format(interface))


def start_olsrd(interface: str):
    """
    Starts OLSRd on given interface.
    Returns the process info of the started OLSRd process.
    """
    path = os.path.dirname(os.path.abspath(__file__))
    configfile = path + '/' + interface + '-olsrd.conf'
    # Wait for the interface to be in UP or DORMANT state
    stdout, stderr = cmd_ip_link_show(interface)
    while b'state DOWN' in stdout:
        stdout, stderr = cmd_ip_link_show(interface)
    log.info("*** {}: Starting OLSR".format(interface))
    stdout, stderr = Popen(["olsrd", "-f", configfile, "-d", "0"], stdout=PIPE, stderr=PIPE).communicate()
    stdout, stderr = Popen("pgrep -a olsrd | grep " + interface, shell=True, stdout=PIPE, stderr=PIPE).communicate()
    return stdout


def reconnect_to_access_point(interface: str, olsrd_pid: int, ssid: str, qdisc_rate: int, qdisc_unit: str):
    """
    Connects to the AP if the SSID is in range.
    Returns 0 after successful reconnect.
    """
    if qdisc_rate > 0:
        rate, unit = qdisc_rate, qdisc_unit
        print("*** Updating qdisc with HTB rate {} {}".format(rate, unit))
        update_qdisc(interface, rate, unit)
        log.info("*** {}: Qdisc updated with HTB rate {} {}".format(args.interface, rate, unit))
    if olsrd_pid > 0:
        log.info("*** {}: OLSR runnning: Killing olsrd process (PID: {})".format(interface, olsrd_pid))
        olsrd_pid = stop_olsrd(interface, olsrd_pid)
    stdout, stderr = cmd_iw_dev(interface, "connect", ssid)
    log.info("*** {}: Connected interface to {}".format(interface, ssid))
    if qdisc_rate > 0:
        rate, unit = 1, 'mbit'
        print("*** Updating qdisc with HTB rate {} {}".format(rate, unit))
        update_qdisc(interface, rate, unit)
        log.info("*** {}: Qdisc updated with HTB rate {} {}".format(args.interface, rate, unit))
    return olsrd_pid


def stop_olsrd(interface: str, pid: int):
    """
    Stops OLSR and configures the wifi interface for a reconnection to the AP.
    """
    os.kill(pid, signal.SIGTERM)
    log.info("*** {}: Killed given olsrd process (PID: {})".format(interface, pid))
    stdout, stderr = cmd_iw_dev(interface, "ibss", "leave")
    log.info("*** {}: IBSS leave completed".format(interface))
    stdout, stderr = cmd_iw_dev(interface, "set", "type", "managed")
    log.info("*** {}: Set type to managed".format(interface))
    return 0


def write_signal_to_file(signal_data: dict, file: str):
    csv_columns = ['time', 'SSID', 'signal', 'signal_avg', 'rx_bitrate', 'tx_bitrate']
    write_or_append_csv_to_file(signal_data, csv_columns, file)


def log_event(event: str, value: int, start_time: float, path: str, station: str):
    csv_columns = ['time', 'disconnect', 'reconnect', 'scanner_start', 'scanner_stop', 'scan_trigger']
    data = {k: 0 for k in csv_columns}
    data.update({'time': datetime.now().timestamp() - start_time, event: value})
    file = path + station + '_events.csv'
    write_or_append_csv_to_file(data, csv_columns, file)


def write_or_append_csv_to_file(data: dict, csv_columns: list, file: str):
    if os.path.isfile(file):
        with open(file, 'a') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writerow(data)
    else:
        with open(file, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            writer.writerow(data)


# function to create the qdisc
def init_qdisc(interface: str, rate: float, rate_unit: str, latency: float = 2.0, latency_unit: str = 's'):
    # deleting rules
    subprocess.call('tc qdisc del dev ' + interface + ' root', shell=True)
    # increasing the queue len - Root qdisc and default queue length:
    subprocess.call('ip link set dev ' + interface + ' txqueuelen 10000', shell=True)
    subprocess.call('tc qdisc add dev ' + interface + ' root handle 1: htb default 1', shell=True)
    subprocess.call('tc class add dev ' + interface + ' parent 1: classid 1:1 htb rate ' + str(rate) + rate_unit, shell=True)  # ceil 1mbit
    # subprocess.call('tc class add dev ' + interface + ' parent 1:1 classid 1:2 htb rate ' + str(rate) + rate_unit,
    #                 shell=True)
    # subprocess.call('tc qdisc add dev ' + interface + ' parent 1:2 handle 2: netem delay ' + str(latency) + latency_unit,
    #                 shell=True)


def update_qdisc(interface: str, rate: float, rate_unit: str):
    """Updates the HTB rate of the qdisc (Minimum: 8 bit)"""
    subprocess.call('tc class replace dev ' + interface + ' parent 1: classid 1:1 htb rate ' +
                    str(rate) + rate_unit, shell=True)


def sleep_and_ping(sleep_interval: float, ip: str):
    time.sleep(sleep_interval)
    subprocess.Popen(["ping", "-c1", ip]).communicate()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Signal monitoring app")
    parser.add_argument("-i", "--interface", help="The interface to be monitored", type=str, required=True)
    parser.add_argument("-p", "--pingto", help="Define an address to ping after activating OLSR to test", type=str,
                        default=None)
    parser.add_argument("-s", "--scaninterval", help="Time interval in seconds (float) for scanning if the wifi access "
                                                     "point is in range while being in adhoc mode (default: 10.0)",
                        type=float, default=10.0)
    parser.add_argument("-d", "--disconnectthreshold", help="Signal strength (float) below which station dissconnects "
                                                            "from AP and activates OLSR (default: -88.0 dBm)",
                        type=float, default=-88.0)
    parser.add_argument("-r", "--reconnectthreshold", help="Minimal signal strength (float) of AP required for trying "
                                                           "reconnect (default: -85.0 dBm)", type=float, default=-85.0)
    parser.add_argument("-A", "--apssid", help="SSID of the access point (default: ap1-ssid)", type=str,
                        default="ap1-ssid")
    parser.add_argument("-B", "--apbssid", help="BSSID of the access point (default: 00:00:00:00:01:00)", type=str,
                        default="00:00:00:00:01:00")
    parser.add_argument("-I", "--apip", help="IP address of the access point", type=str, default="10.0.0.10")
    parser.add_argument("-o", "--outputpath", help="Path to save statistics in", type=str, required=True)
    parser.add_argument("-S", "--scaninterface", help="Interface to use for active scans for reconnection to AP",
                        type=str)
    parser.add_argument("-w", "--signalwindow", help="Window for the moving average calculation of the signal strength", type=int, default=3)
    parser.add_argument("-t", "--starttime", help="Timestamp of the start of the experiment as synchronizing reference for measurements", type=float, required=True)
    parser.add_argument("-O", "--noolsr", help="Do not use olsr when connection to AP is lost (default: False)", action='store_true', default=False)
    parser.add_argument("-q", "--qdisc", help="Bandwidth in bits/s to throttle qdisc to during handover. 0 means deactivate qdisc (default: 0)", type=int, default=0)
    args = parser.parse_args()

    log_format = logging.Formatter(fmt='%(levelname)-8s [%(asctime)s]: %(message)s')
    ch = logging.StreamHandler()
    starttime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = os.path.dirname(os.path.abspath(__file__))
    log.setLevel(logging.DEBUG)
    log_fh = logging.FileHandler(path + '/data/logs/' + starttime + '_debug.log')
    log_fh.setLevel(logging.DEBUG)
    log_fh.setFormatter(log_format)
    log.addHandler(log_fh)
    log.info('*** Started monitoring_signal.py')

    main(args)
