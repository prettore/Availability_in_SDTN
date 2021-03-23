import os
import signal
import argparse
import subprocess
import time
import csv
import logging
import re
import threading

from subprocess import Popen, PIPE
from datetime import datetime

from cmd_utils import cmd_iw_dev, cmd_ip_link_set, cmd_ip_link_show
from scanner import Scanner

log = logging.getLogger('logger')


def main():
    """
    This program monitors the signal strength of the connected wifi access point (AP).
    When the signal is lost the program activates OLSR on the wifi interface.
    While OLSR is activated the program continuously scans for the APs SSID to reappear in range.
    When the APs SSID is again in range the program deactivates OLSR and reconnects to the AP.
    """
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
    parser.add_argument("-S", "--apssid", help="SSID of the access point (default: ap1-ssid)", type=str,
                        default="ap1-ssid")
    parser.add_argument("-B", "--apbssid", help="BSSID of the access point (default: 00:00:00:00:01:00)", type=str,
                        default="00:00:00:00:01:00")
    parser.add_argument("-I", "--apip", help="IP address of the access point", type=str, default="10.0.0.10")
    parser.add_argument("-o", "--outputpath", help="Path to save statistics in", type=str, required=True)
    args = parser.parse_args()

    path = os.path.dirname(os.path.abspath(__file__))
    statistics_dir = path + '/data/statistics/' + args.outputpath + '/'
    if not os.path.isdir(statistics_dir):
        os.makedirs(statistics_dir)
    flexible_sdn_olsr(args.interface, args.scaninterval, args.reconnectthreshold, args.disconnectthreshold, args.pingto,
                      statistics_dir, args.apssid, args.apbssid, args.apip)


def flexible_sdn_olsr(interface: str, scan_interval: float, reconnect_threshold: float, disconnect_threshold: float,
                      pingto: str, out_path: str, ap_ssid: str, ap_bssid: str, ap_ip: str):
    """
    This function monitors the wifi signal strength as long there is a connection to the AP.
    When the connection is lost it starts the OLSR and continuously scans for the AP to reappear.
    When the AP reappears OLSR is deactivated and a connection to the AP will be established.
    """
    scanner = Scanner(interface, scan_interval, ap_ssid)
    olsrd_pid = 0
    csv_columns = ['time', 'ssid', 'signal', 'signal_avg', 'rx_bitrate', 'tx_bitrate', 'expected_throughput']
    start_time = datetime.now()
    file = out_path + interface + '_signal.csv'
    stdout, stderr = cmd_iw_dev(interface, "link")
    while b'Not connected.' in stdout and b'Connected to ' + ap_bssid.encode() not in stdout:
        stdout, stderr = cmd_iw_dev(interface, "link")
    stdout, stderr = Popen(["ping", "-c1", ap_ip], stdout=PIPE, stderr=PIPE).communicate()
    if pingto:
        Popen(["ping", "-c1", pingto]).communicate()
    print("ssid, time, signal")
    while True:
        time.sleep(1)
        stdout, stderr = cmd_iw_dev(interface, "link")
        stdout = stdout.decode()
        signal = signal_strength_from_link_info(stdout, ap_bssid, ap_ssid)
        if 'Connected to ' + ap_bssid in stdout and signal and signal >= disconnect_threshold:
            data = get_signal_quality(interface, ap_bssid, ap_ssid)
            if data:
                data.update({'time': datetime.now().timestamp()})
                print("{}, {}, {}".format(data['ssid'], data['time'], data['signal']))
                if os.path.isfile(file):
                    with open(file, 'a') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
                        writer.writerow(data)
                else:
                    with open(file, 'w') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
                        writer.writeheader()
                        writer.writerow(data)
        else:
            print("*** AP signal too weak or connection lost (signal: {} / {})".format(signal, disconnect_threshold))
            if not scanner.is_alive():
                print("*** Starting background scan")
                scanner.start()
            reconnected, olsrd_pid = try_reconnect(interface, olsrd_pid, ssid=ap_ssid, bssid=ap_bssid,
                                                   threshold=reconnect_threshold)
            if not reconnected and olsrd_pid == 0:
                print("*** Starting OLSRd")
                olsrd_pid = start_olsrd(interface)
                if pingto:
                    spthread = threading.Thread(target=sleep_and_ping, kwargs={'sleep_interval': 1.0, 'ip': pingto},
                                                daemon=True)
                    spthread.start()
            if reconnected:
                if scanner.is_alive():
                    print("*** Stopping background scan")
                    scanner.terminate()
                    scanner = Scanner(interface, scan_interval, ap_ssid)
                time.sleep(2)
                print("*** Reconnected to AP.")
                print("*** OLSRd PID: ", olsrd_pid)
                stdout, stderr = Popen(["ping", "-c1", ap_ip], stdout=PIPE, stderr=PIPE).communicate()


def get_signal_quality(interface: str, bssid: str, ssid: str):
    """
    Monitor the signal strength on a given wifi interface as long as it is connected to an AP with the hard coded MAC
    address.
    Returns the signal data if the connection is present.
    Returns None if the AP is not connected.
    """
    stdout, stderr = cmd_iw_dev(interface, "station", "dump")
    data = stdout.decode()
    if 'Station ' + bssid in data:
        data = list(filter(None, data.split('\n\t')[1:]))
        data = dict(map(lambda s: s.split(':'), data))
        signal_data = {k.replace(' ', '_'): (data[k].strip() if k in data else 'NaN') for k in ['signal', 'signal avg',
                                                                                                'rx bitrate',
                                                                                                'tx bitrate',
                                                                                                'expected throughput']}
        signal_data.update({'ssid': ssid})
        return signal_data
    return None


def start_olsrd(interface: str):
    """
    Configures the given wifi interface for OLSR and activates OLSR.
    The configuration for OLSR is defined in the ibss dict.
    Returns the Popen object of the olsrd process after starting olsrd in the background.
    The Popen object can be used to kill the process later.
    """
    path = os.path.dirname(os.path.abspath(__file__))
    configfile = path + '/' + interface + '-olsrd.conf'
    ibss = {'ssid': 'adhocNet', 'freq': '2432', 'ht_cap': 'HT40+', 'bssid': '02:CA:FF:EE:BA:01'}
    stdout, stderr = cmd_iw_dev(interface, "set", "type", "ibss")
    log.info("*** {}: Set type to ibss".format(interface))
    stdout, stderr = cmd_ip_link_set(interface, "up")
    log.info("*** {}: Set ip link up".format(interface))
    stdout, stderr = cmd_iw_dev(interface, "ibss", "join", ibss['ssid'], ibss['freq'], ibss['ht_cap'], ibss['bssid'])
    log.info("*** {}: Join ibss adhocNet".format(interface))
    # Wait for the interface to be in UP or DORMANT state
    stdout, stderr = cmd_ip_link_show(interface)
    while b'state DOWN' in stdout:
        stdout, stderr = cmd_ip_link_show(interface)
    log.info("*** {}: Starting OLSR".format(interface))
    stdout, stderr = Popen(["olsrd", "-f", configfile, "-d", "0"], stdout=PIPE, stderr=PIPE).communicate()
    log.info("*** {}: Started olsrd in the background (PID: )".format(interface))
    stdout, stderr = Popen("pgrep -a olsrd | grep " + interface, shell=True, stdout=PIPE, stderr=PIPE).communicate()
    if stdout:
        olsrd_pid = int(stdout.split()[0])
        print("*** OLSRd running (PID: {})".format(olsrd_pid))
        return olsrd_pid
    return 1


def try_reconnect(interface: str, olsrd_pid: int, ssid: str, bssid: str, threshold: float):
    """
    Scans for the APs SSID and connects to the AP if the SSID is in range.
    Returns True if AP is in range and has been connected.
    Returns False if the AP is not in range.
    """
    log.info("*** {}: Collecting scan dump for {}".format(interface, ssid))
    stdout, stderr = cmd_iw_dev(interface, "scan", "dump")
    data = stdout.decode()
    if "BSS " + bssid in data and "SSID: " + ssid in data:
        signal = signal_strength_from_scan_dump(data, bssid, ssid)
        print("*** {}: Scan detected {} in range (signal: {} / {})".format(interface, ssid, signal, threshold))
        log.info("*** {}: Scan detected {} in range (signal: {} / {})".format(interface, ssid, signal, threshold))
        if signal and signal >= threshold:
            log.info("*** {}: Scan result: {} in range with signal {}".format(interface, ssid, signal))
            if olsrd_pid > 0:
                log.info("*** {}: OLSR runnning: Killing olsrd process (PID: {})".format(interface, olsrd_pid))
                olsrd_pid = stop_olsrd(interface, olsrd_pid)
            stdout, stderr = cmd_iw_dev(interface, "connect", ssid)
            log.info("*** {}: Connected interface to {}".format(interface, ssid))
            return True, olsrd_pid
    return False, olsrd_pid


def signal_strength_from_link_info(data: str, bssid: str, ssid: str):
    if 'Connected to ' + bssid in data:
        for d in data.split('Connected to '):
            signal = extract_signal_strength(d, bssid, ssid)
            if signal:
                return signal
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


def sleep_and_ping(sleep_interval: float, ip: str):
    time.sleep(sleep_interval)
    subprocess.Popen(["ping", "-c1", ip]).communicate()


if __name__ == '__main__':
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
    main()
