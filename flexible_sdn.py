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
    cmd_iw_dev(args.interface, "connect", args.apssid)
    if args.scaninterface:
        scaninterface = args.scaninterface
    else:
        scaninterface = args.interface
    path = os.path.dirname(os.path.abspath(__file__))
    statistics_dir = path + '/data/statistics/' + args.outputpath + '/'
    if not os.path.isdir(statistics_dir):
        os.makedirs(statistics_dir)

    if args.qdiscdisconnect > 0 and args.qdiscreconnect > 0:
        rate, unit = 1, 'mbit'
        print("*** Setting up qdisc with HTB rate {} {}".format(rate, unit))
        init_qdisc(args.interface, rate, unit)
        log.info("*** {}: Qdisc set up with HTB rate {} {}".format(args.interface, rate, unit))
        qdisc = 'on'
        qdisc_rates = {'standard': 1, 'std_unit': 'mbit', 'disconnect': args.qdiscdisconnect,
                       'reconnect': args.qdiscreconnect, 'throttle_unit': 'bit', 'throttled': False}
    else:
        qdisc = 'off'
        qdisc_rates = {'disconnect': 0, 'reconnect': 0, 'unit': 'bit'}
    if args.noolsr:
        olsr = 'off'
    else:
        olsr = 'on'
    parameters = {'start_time': args.starttime, 'OLSR': olsr, 'interface': args.interface,
                  'qdisc': {'mode': qdisc, 'rates': qdisc_rates},
                  'AP': {'ssid': args.apssid, 'bssid': args.apbssid, 'ip': args.apip},
                  'scan': {'interface': scaninterface, 'interval': args.scaninterval,
                           'moving_avg_window': args.signalwindow,
                           'reconnect_threshold': args.reconnectthreshold,
                           'disconnect_threshold': args.disconnectthreshold}}
    with open(statistics_dir + 'start_params.json', 'w') as file:
        json.dump(parameters, file, indent=4)
    controller = FlexibleSdnOlsrController(args.interface, scaninterface, args.scaninterval, args.reconnectthreshold,
                                           args.disconnectthreshold, args.pingto, statistics_dir, args.apssid,
                                           args.apbssid, args.apip, args.signalwindow, args.starttime, qdisc_rates,
                                           args.noolsr)
    controller.run_controller()


class FlexibleSdnOlsrController:
    def __init__(self, interface: str, scaninterface: str, scan_interval: float, reconnect_threshold: float,
                 disconnect_threshold: float, pingto: str, out_path: str, ap_ssid: str, ap_bssid: str, ap_ip: str,
                 signal_window: int, start_time: float, qdisc: dict, no_olsr: bool = False):
        self.interface = interface
        self.station = interface.split('-')[0]
        self.scan_interface = scaninterface
        self.scan_interval = scan_interval
        self.reconnect_threshold = reconnect_threshold
        self.disconnect_threshold = disconnect_threshold
        self.pingto = pingto
        self.out_path = out_path
        self.signal_file = out_path + interface + '_signal.csv'
        self.ap_ssid = ap_ssid
        self.ap_bssid = ap_bssid
        self.ap_ip = ap_ip
        self.signal_window = signal_window
        self.start_time = start_time
        self.qdisc = qdisc
        self.qdisc.update({'throttled': False})
        self.no_olsr = no_olsr
        self.olsrd_pid = 0
        self.link_signal_deque = deque(maxlen=signal_window)
        self.scan_signal_deque = deque(maxlen=signal_window)
        self.scanner = Scanner(scaninterface, scan_interval, out_path, self.station, start_time, ap_ssid)

        log.info("*** {}: Interface: {}, Scan-interface: {}".format(interface.split('-')[0], interface, scaninterface))
        stdout, stderr = cmd_iw_dev(interface, "link")
        while b'Connected to ' + ap_bssid.encode() not in stdout:
            stdout, stderr = cmd_iw_dev(interface, "link")
        stdout, stderr = Popen(["ping", "-c1", ap_ip], stdout=PIPE, stderr=PIPE).communicate()
        if self.pingto:
            Popen(["ping", "-c1", pingto]).communicate()

    def run_controller(self):
        print("ssid, time (s), signal (dBm), signal_avg (dBm)")
        while True:
            time.sleep(1)
            ap_link_signal = self.get_link_signal_quality()
            if ap_link_signal:
                signal = float(ap_link_signal['signal'].rstrip(' dBm'))
                self.link_signal_deque.append(signal)
                ap_link_signal.update({'signal': signal,
                                       'signal_avg': sum(self.link_signal_deque) / len(self.link_signal_deque)})
                if ap_link_signal['signal_avg'] >= self.disconnect_threshold:
                    print("{}, {}, {}, {:.2f}".format(ap_link_signal['SSID'], ap_link_signal['time'],
                                                      ap_link_signal['signal'], ap_link_signal['signal_avg']))
                    self.write_signal_to_file(ap_link_signal)
                    # if self.qdisc['disconnect'] > 0:
                    #     if ap_link_signal['signal_avg'] <= self.disconnect_threshold + 2 and not self.qdisc['throttled']:
                    #         update_qdisc(self.interface, self.qdisc['disconnect'], self.qdisc['throttle_unit'])
                    #         self.qdisc.update({'throttled': True})
                    #     elif ap_link_signal['signal_avg'] > self.disconnect_threshold + 2 and self.qdisc['throttled']:
                    #         update_qdisc(self.interface, self.qdisc['standard'], self.qdisc['std_unit'])
                    #         self.qdisc.update({'throttled': False})
                    continue
            if not self.scanner.is_alive():
                if ap_link_signal:
                    print("*** AP signal too weak (last signal: {} / {})".format(ap_link_signal['signal'],
                                                                                 self.disconnect_threshold))
                else:
                    print("*** AP connection lost")
                print("*** Starting background scan")
                self.scanner.start()
                self.log_event('scanner_start', 1)
            scan_signal = self.get_scan_dump_signal()
            if scan_signal and 'signal' in scan_signal:
                self.scan_signal_deque.append(scan_signal['signal'])
                scan_signal.update({'signal_avg': sum(self.scan_signal_deque) / len(self.scan_signal_deque)})
                log.info("*** {}: Scan detected {} in range (signal: {} / {})".format(self.scan_interface, self.ap_ssid,
                                                                                      scan_signal['signal'],
                                                                                      self.reconnect_threshold))
                self.write_signal_to_file(scan_signal)
                print("{}, {}, {}, {:.2f}".format(scan_signal['SSID'], scan_signal['time'], scan_signal['signal'],
                                                  scan_signal['signal_avg']))
                if scan_signal['signal'] >= self.reconnect_threshold:
                    self.log_event('reconnect', 1)
                    self.reconnect_to_access_point()
                    self.log_event('reconnect', 2)
                    if self.scanner.is_alive():
                        print("*** Stopping background scan")
                        self.scanner.terminate()
                        self.log_event('scanner_stop', 1)
                        self.scanner = Scanner(self.scan_interface, self.scan_interval, self.out_path, self.station,
                                               self.start_time, self.ap_ssid)
                    time.sleep(0.5)
                    print("*** Reconnected to AP.")
                    print("*** OLSRd PID: ", self.olsrd_pid)
                    stdout, stderr = Popen(["ping", "-c1", self.ap_ip], stdout=PIPE, stderr=PIPE).communicate()
                    continue
            if self.olsrd_pid == 0 and not self.no_olsr:
                print("*** Starting OLSRd")
                self.log_event('disconnect', 1)
                self.switch_to_olsr()
                self.log_event('disconnect', 2)
                if self.pingto:
                    spthread = threading.Thread(target=sleep_and_ping,
                                                kwargs={'sleep_interval': 1.0, 'ip': self.pingto},
                                                daemon=True)
                    spthread.start()
            elif self.no_olsr:
                self.log_event('disconnect', 1)
                cmd_iw_dev(self.interface, 'disconnect')
                self.log_event('disconnect', 2)

    def get_link_signal_quality(self):
        """
        Fetches the signal strength on a given wifi interface as long as it is connected to an AP with a matching ssid.
        Returns the signal data if the connection is present.
        Returns None if the AP is not connected.
        """
        stdout, stderr = cmd_iw_dev(self.interface, "link")
        data = stdout.decode()
        if 'Connected to ' + self.ap_bssid in data and 'SSID: ' + self.ap_ssid in data:
            data = [x for x in list(filter(None, data.split('\n\t')[1:])) if x.strip()]
            data = dict(map(lambda s: s.split(':'), data))
            signal_data = {k.replace(' ', '_'): (data[k].strip() if k in data else 'NaN') for k in ['SSID', 'signal',
                                                                                                    'rx bitrate',
                                                                                                    'tx bitrate']}
            signal_data.update({'time': datetime.now().timestamp() - self.start_time})
            return signal_data
        return None

    def write_signal_to_file(self, signal_data: dict):
        csv_columns = ['time', 'SSID', 'signal', 'signal_avg', 'rx_bitrate', 'tx_bitrate']
        write_or_append_csv_to_file(signal_data, csv_columns, self.signal_file)

    def get_scan_dump_signal(self):
        stdout, stderr = cmd_iw_dev(self.scan_interface, "scan", "dump")
        scan_data = stdout.decode()
        if "BSS " + self.ap_bssid in scan_data and "SSID: " + self.ap_ssid in scan_data:
            scan_signal = self.signal_strength_from_scan_dump(scan_data)
            scan_data = {'time': datetime.now().timestamp() - self.start_time, 'signal': scan_signal,
                         'SSID': self.ap_ssid, 'rx_bitrate': 0, 'tx_bitrate': 0}
            return scan_data
        return None

    def signal_strength_from_scan_dump(self, data: str):
        for d in data.split('BSS '):
            signal = self.extract_signal_strength(d)
            if signal:
                return signal
        return None

    def extract_signal_strength(self, data: str):
        if data.startswith(self.ap_bssid) and 'SSID: ' + self.ap_ssid in data:
            entry = list(filter(None, data.split('\n\t')[1:]))
            entry = dict(map(lambda x: (x.split(':', 1) + [''])[:2], entry))
            signal = entry['signal'].strip()
            signal = re.findall(r"[-+]?\d+\.\d*|[-+]?\d+|[-+]?\.\d+", signal)
            if signal:
                return float(signal[0])
        return None

    def log_event(self, event: str, value: int):
        csv_columns = ['time', 'disconnect', 'reconnect', 'scanner_start', 'scanner_stop', 'scan_trigger']
        data = {k: 0 for k in csv_columns}
        data.update({'time': datetime.now().timestamp() - self.start_time, event: value})
        file = self.out_path + self.station + '_events.csv'
        write_or_append_csv_to_file(data, csv_columns, file)

    def reconnect_to_access_point(self):
        """
        Connects to the AP if the SSID is in range.
        Returns 0 after successful reconnect.
        """
        if self.qdisc['reconnect'] > 0:
            update_qdisc(self.interface, self.qdisc['reconnect'], self.qdisc['throttle_unit'])
            self.qdisc.update({'throttled': True})
        if self.olsrd_pid > 0:
            log.info("*** {}: OLSR runnning: Killing olsrd process (PID: {})".format(self.interface, self.olsrd_pid))
            self.stop_olsrd()
        stdout, stderr = cmd_iw_dev(self.interface, "connect", self.ap_ssid)
        log.info("*** {}: Connected interface to {}".format(self.interface, self.ap_ssid))
        if self.qdisc['reconnect'] > 0:
            update_qdisc(self.interface, self.qdisc['standard'], self.qdisc['std_unit'])
            self.qdisc.update({'throttled': False})

    def stop_olsrd(self):
        """
        Stops OLSR and configures the wifi interface for a reconnection to the AP.
        """
        os.kill(self.olsrd_pid, signal.SIGTERM)
        log.info("*** {}: Killed given olsrd process (PID: {})".format(self.interface, self.olsrd_pid))
        stdout, stderr = cmd_iw_dev(self.interface, "ibss", "leave")
        log.info("*** {}: IBSS leave completed".format(self.interface))
        stdout, stderr = cmd_iw_dev(self.interface, "set", "type", "managed")
        log.info("*** {}: Set type to managed".format(self.interface))
        self.olsrd_pid = 0

    def switch_to_olsr(self):
        """
        Configures the given wifi interface for OLSR and starts OLSRd in the background.
        Returns the PID of the OLSRd process.
        """
        if self.qdisc['disconnect'] > 0 and not self.qdisc['throttled']:
            update_qdisc(self.interface, self.qdisc['disconnect'], self.qdisc['throttle_unit'])
            self.qdisc.update({'throttled': True})
        self.prepare_olsrd(self.interface)
        self.start_olsrd()
        if self.qdisc['disconnect'] > 0:
            update_qdisc(self.interface, self.qdisc['standard'], self.qdisc['std_unit'])
            self.qdisc.update({'throttled': False})

    def prepare_olsrd(self, interface: str):
        """
        Configures the given interface for ad-hoc mode and joins IBSS.
        """
        ibss = {'ssid': 'adhocNet', 'freq': '2432', 'ht_cap': 'HT40+', 'bssid': '02:CA:FF:EE:BA:01'}
        stdout, stderr = cmd_iw_dev(interface, "set", "type", "ibss")
        log.info("*** {}: Set type to ibss".format(interface))
        stdout, stderr = cmd_ip_link_set(interface, "up")
        log.info("*** {}: Set ip link up".format(interface))
        stdout, stderr = cmd_iw_dev(interface, "ibss", "join", ibss['ssid'], ibss['freq'], ibss['ht_cap'],
                                    ibss['bssid'])
        log.info("*** {}: Join ibss adhocNet".format(interface))

    def start_olsrd(self):
        """
        Starts OLSRd on given interface.
        Returns the process info of the started OLSRd process.
        """
        path = os.path.dirname(os.path.abspath(__file__))
        configfile = path + '/' + self.interface + '-olsrd.conf'
        # Wait for the interface to be in UP or DORMANT state
        stdout, stderr = cmd_ip_link_show(self.interface)
        while b'state DOWN' in stdout:
            stdout, stderr = cmd_ip_link_show(self.interface)
        log.info("*** {}: Starting OLSR".format(self.interface))
        stdout, stderr = Popen(["olsrd", "-f", configfile, "-d", "0"], stdout=PIPE, stderr=PIPE).communicate()
        stdout, stderr = Popen("pgrep -a olsrd | grep " + self.interface, shell=True, stdout=PIPE, stderr=PIPE).communicate()
        if stdout:
            self.olsrd_pid = int(stdout.split()[0])
            log.info("*** {}: Started olsrd in the background (PID: )".format(self.interface, self.olsrd_pid))
            print("*** OLSRd running (PID: {})".format(self.olsrd_pid))
        else:
            log.info("*** {}: Starting olsrd failed".format(self.interface))
            print("*** Starting OLSRd failed!")


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
    print("*** Updating qdisc with HTB rate {} {}".format(rate, rate_unit))
    subprocess.call('tc class replace dev ' + interface + ' parent 1: classid 1:1 htb rate ' +
                    str(rate) + rate_unit, shell=True)
    log.info("*** {}: Qdisc updated with HTB rate {} {}".format(interface, rate, rate_unit))


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
                        type=float, default=5.0)
    parser.add_argument("-d", "--disconnectthreshold", help="Signal strength (float) below which station dissconnects "
                                                            "from AP and activates OLSR (default: -88.0 dBm)",
                        type=float, default=-70.0)
    parser.add_argument("-r", "--reconnectthreshold", help="Minimal signal strength (float) of AP required for trying "
                                                           "reconnect (default: -85.0 dBm)", type=float, default=-65.0)
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
    parser.add_argument("-qd", "--qdiscdisconnect",
                        help="Bandwidth in bits/s to throttle qdisc to during handover AP to OLSR. 0 means deactivate qdisc (default: 0)",
                        type=int, default=0)
    parser.add_argument("-qr", "--qdiscreconnect",
                        help="Bandwidth in bits/s to throttle qdisc to during handover AP to OLSR. 0 means deactivate (default: 0)",
                        type=int, default=0)
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
    log.info('*** {}: Started flexible_sdn.py'.format(args.interface))

    main(args)
