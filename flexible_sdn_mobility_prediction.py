import os
import signal
import logging
import argparse
import subprocess
import json
import csv
from collections import deque
from datetime import datetime
from typing import Optional

import pandas as pd
from time import sleep
from subprocess import Popen, PIPE

from cmd_utils import cmd_iw_dev, cmd_ip_link_set, cmd_ip_link_show


log = logging.getLogger('logger')


def main(args: argparse.Namespace):
    statistics_dir = args.statisticsdir
    # df_trace = TraceReaderMobilityPrediction.read_trace(args.tracefile)

    print("*** Initial connect to AP")
    cmd_iw_dev(args.interface, "connect", args.apssid)

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
    parameters = {'start_time': args.starttime, 'interface': args.interface,
                  'qdisc': {'mode': qdisc, 'rates': qdisc_rates},
                  'AP': {'ssid': args.apssid, 'bssid': args.apbssid, 'ip': args.apip}}
    with open(statistics_dir + args.interface.split('-')[0] + '_start-params.json', 'w') as file:
        json.dump(parameters, file, indent=4)

    controller = FlexibleSdnOlsrControllerNetState(args.interface, args.ip, args.apssid, args.apbssid, args.apip, args.pingto,
                                                   args.starttime, qdisc_rates, args.state_file,
                                                   args.disconnect_threshold, args.reconnect_threshold, args.statisticsdir)
    controller.run_controller()


class FlexibleSdnOlsrControllerNetState:
    columns = {'time': float, 'x': float, 'y': float, 'state': int,
               'x_pred': float, 'y_pred': float, 'state_pred': float,
               'dtime': float}

    def __init__(self, interface: str, ip: str, ap_ssid: str, ap_bssid: str, ap_ip: str, pingto: str, start_time: float,
                 qdisc: dict, state_file: str, disconnect_threshold: float, reconnect_threshold: float, statistics_dir: str):
        self.out_path = statistics_dir
        self.interface = interface
        self.ip = ip
        self.station = interface.split('-')[0]
        self.connected_to_ap = None
        self.pingto = pingto
        self.ap_ssid = ap_ssid
        self.ap_bssid = ap_bssid
        self.ap_ip = ap_ip
        self.start_time = start_time
        self.qdisc = qdisc
        self.qdisc.update({'throttled': False})
        self.olsrd_pid = 0
        self.state_file = f"{state_file}"
        self.state_change_stamp = 0
        self.disconnect_threshold = disconnect_threshold
        self.reconnect_threshold = reconnect_threshold
        self.window_size = 10
        self.sliding_window = deque(maxlen=self.window_size)
        self.current_state = pd.read_csv(self.state_file, dtype=self.columns).tail(1).reset_index().loc[0].to_dict()

        log.info("*** {}: Interface: {}".format(interface.split('-')[0], interface))
        if self.current_state['state'] > 1:
            self.initial_connect_to_ap()
            self.connected_to_ap = True
        else:
            self.initial_connect_to_olsr()
            self.connected_to_ap = False

    def run_controller(self):
        while True:
            sleep(0.1)
            new_state = self.has_state_changed()
            if new_state is not None:
                self.sliding_window.append(new_state['state_pred'])
                if self.connected_to_ap:
                    net_status = "AP"
                else:
                    net_status = "MANET"
                print(f"*** New state: {new_state} - {net_status}")
                if self.connected_to_ap and (sum(self.sliding_window) / len(self.sliding_window)) <= self.disconnect_threshold:
                    print("*** Starting OLSRd")
                    self.log_event('disconnect', 1)
                    self.switch_to_olsr()
                    self.connected_to_ap = False
                    self.log_event('disconnect', 2)
                    print("*** Reconnected to AP.")
                if not self.connected_to_ap and (sum(self.sliding_window) / len(self.sliding_window)) > self.reconnect_threshold:
                    print("*** Reconnecting to AP")
                    self.log_event('reconnect', 1)
                    self.reconnect_to_access_point()
                    self.connected_to_ap = True
                    self.log_event('reconnect', 2)

    def has_state_changed(self) -> Optional[dict]:
        state_change_stamp = os.stat(self.state_file).st_mtime_ns
        if state_change_stamp != self.state_change_stamp:
            new_state = pd.read_csv(self.state_file, dtype=self.columns).tail(1).reset_index().loc[0].to_dict()
            if new_state != self.current_state:
                return new_state
        return None

    def initial_connect_to_ap(self):
        log.info(f"*** {self.interface}: Initially connecting to AP {self.ap_ssid} ...")
        stdout, stderr = cmd_iw_dev(self.interface, "connect", self.ap_ssid)
        stdout, stderr = subprocess.Popen(["ifconfig", self.interface, self.ip, "netmask", "255.255.255.0"], stdout=PIPE,
                                          stderr=PIPE).communicate()
        stdout, stderr = cmd_iw_dev(self.interface, "link")
        print("*** Checking connection to AP...")
        while b'Connected to ' + self.ap_bssid.encode() not in stdout:
            stdout, stderr = cmd_iw_dev(self.interface, "link")
            print(stdout)
            sleep(0.5)
        print("*** Connected to AP")
        log.info(f"*** {self.interface}: Initial connection to AP successfull")
        stdout, stderr = Popen(["ping", "-c1", self.ap_ip], stdout=PIPE, stderr=PIPE).communicate()
        if self.pingto:
            Popen(["ping", "-c1", self.pingto]).communicate()

    def initial_connect_to_olsr(self):
        self.prepare_olsrd(self.interface)
        self.start_olsrd()

    def reconnect_to_access_point(self):
        """
        Connects to the AP if the SSID is in range.
        Returns 0 after successful reconnect.
        """
        if self.qdisc['reconnect'] > 0:
            update_qdisc(self.interface, self.qdisc['reconnect'], self.qdisc['throttle_unit'])
            self.qdisc.update({'throttled': True})
        # Rettore
        if self.olsrd_pid > 0:# and not self.no_olsr:
            log.info(f"*** {self.interface}: OLSR runnning: Killing olsrd process (PID: {self.olsrd_pid})")
            self.stop_olsrd()
        log.info(f"*** {self.interface}: Connecting to AP {self.ap_ssid} ...")
        connection_successfull = False
        while not connection_successfull:
            stdout, stderr = cmd_iw_dev(self.interface, "connect", self.ap_ssid)
            for i in range(10):
                sleep(0.1)
                stdout, stderr = subprocess.Popen(["ifconfig", self.interface, self.ip, "netmask", "255.255.255.0"],
                                                  stdout=PIPE, stderr=PIPE).communicate()
                stdout, stderr = cmd_iw_dev(self.interface, "link")
                if b'Connected to ' + self.ap_bssid.encode() not in stdout:
                    connection_successfull = True
                    break
        log.info(f"*** {self.interface}: Connected interface to {self.ap_ssid}")
        if self.qdisc['reconnect'] > 0:
            update_qdisc(self.interface, self.qdisc['standard'], self.qdisc['std_unit'])
            self.qdisc.update({'throttled': False})

    def stop_olsrd(self):
        """
        Stops OLSR and configures the wifi interface for a reconnection to the AP.
        """
        os.kill(self.olsrd_pid, signal.SIGTERM)
        log.info(f"*** {self.interface}: Killed given olsrd process (PID: {self.olsrd_pid})")
        stdout, stderr = cmd_iw_dev(self.interface, "ibss", "leave")
        log.info(f"*** {self.interface}: IBSS leave completed")
        stdout, stderr = cmd_iw_dev(self.interface, "set", "type", "managed")
        log.info(f"*** {self.interface}: Set type to managed")
        self.olsrd_pid = 0

    def switch_to_olsr(self):
        """
        Configures the given wifi interface for OLSR and starts OLSRd in the background.
        Returns the PID of the OLSRd process.
        """
        if self.qdisc['disconnect'] > 0 and not self.qdisc['throttled']:
            update_qdisc(self.interface, self.qdisc['disconnect'], self.qdisc['throttle_unit'])
            self.qdisc.update({'throttled': True})
        log.info(f"*** {self.interface}: Preparing OLSR connection ...")
        self.prepare_olsrd(self.interface)
        log.info(f"*** {self.interface}: Connecting to MANET ...")
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
        log.info(f"*** {self.interface}: Set type to ibss")
        stdout, stderr = cmd_ip_link_set(self.interface, "up")
        log.info(f"*** {self.interface}: Set ip link up")
        stdout, stderr = cmd_iw_dev(self.interface, "ibss", "join", ibss['ssid'], ibss['freq'], ibss['ht_cap'],
                                    ibss['bssid'])
        log.info(f"*** {self.interface}: Join ibss adhocNet")

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
        log.info(f"*** {self.interface}: Starting OLSR")
        stdout, stderr = Popen(["olsrd", "-f", configfile, "-d", "0"], stdout=PIPE, stderr=PIPE).communicate()
        stdout, stderr = Popen("pgrep -a olsrd | grep " + self.interface, shell=True, stdout=PIPE, stderr=PIPE).communicate()
        if stdout:
            self.olsrd_pid = int(stdout.split()[0])
            log.info(f"*** {self.interface}: Started olsrd in the background (PID: {self.olsrd_pid})")
            print(f"*** OLSRd running (PID: {self.olsrd_pid})")
        else:
            log.info(f"*** {self.interface}: Starting olsrd failed")
            print("*** Starting OLSRd failed!")

    def log_event(self, event: str, value: int):
        csv_columns = ['time', 'disconnect', 'reconnect', 'scanner_start', 'scanner_stop', 'scan_trigger']
        data = {k: 0 for k in csv_columns}
        data.update({'time': datetime.now().timestamp() - self.start_time, event: value})
        file = self.out_path + self.station + '_events.csv'
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
    print("*** Updating qdisc with HTB rate {} {}".format(rate, rate_unit))
    subprocess.call('tc class replace dev ' + interface + ' parent 1: classid 1:1 htb rate ' +
                    str(rate) + rate_unit, shell=True)
    log.info("*** {}: Qdisc updated with HTB rate {} {}".format(interface, rate, rate_unit))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Signal monitoring app")
    parser.add_argument("-i", "--interface", help="The interface to be shaped",
                        type=str, required=True)
    parser.add_argument("-p", "--pingto", help="Define an address to ping after activating OLSR to test",
                        type=str, default=None)
    parser.add_argument("-A", "--apssid", help="SSID of the access point (default: ap1-ssid)", type=str,
                        default="ap1-ssid")
    parser.add_argument("-B", "--apbssid", help="BSSID of the access point (default: 00:00:00:00:01:00)", type=str,
                        default="00:00:00:00:01:00")
    parser.add_argument("-I", "--apip", help="IP address of the access point", type=str, default="10.0.0.10")
    parser.add_argument("-qd", "--qdiscdisconnect",
                        help="Bandwidth in bits/s to throttle qdisc to during handover AP to OLSR. 0 means deactivate qdisc (default: 0)",
                        type=int, default=0)
    parser.add_argument("-qr", "--qdiscreconnect",
                        help="Bandwidth in bits/s to throttle qdisc to during handover AP to OLSR. 0 means deactivate (default: 0)",
                        type=int, default=0)
    parser.add_argument("-s", "--statisticsdir", help="Path to save statistics in", type=str, required=True)
    parser.add_argument("-t", "--starttime", help="Timestamp of the start of the experiment as synchronizing reference for measurements", type=float, required=True)
    parser.add_argument("-f", "--state-file", help="Trace file CP->Node to update the qdisc rule",
                        type=str, required=True)
    parser.add_argument("-w", "--window-size", type=int, required=True, default=10,
                        help="Size of the sliding window to average out the predicted state outliers (default: 10)")
    parser.add_argument("-d", "--disconnect-threshold", type=float, required=True, default=0,
                        help="When this state is predicted while connected to AP, then switch to OLSR connection")
    parser.add_argument("-r", "--reconnect-threshold", type=float, required=True, default=2,
                        help="When this state is predicted while connected to OLSR then switch to AP connection")
    parser.add_argument("--no-realtime", dest="realtime", action="store_false",
                        help="The replay will be faster than realtime by factor 2")
    parser.add_argument("--ip", type=str, required=True)
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = parse_args()
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