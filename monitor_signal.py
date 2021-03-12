import os
import argparse
import subprocess
import time
import csv
import logging

from datetime import datetime
from pathlib import Path
from mininet.log import setLogLevel, info

log = logging.getLogger()


def main():
    path = os.path.dirname(os.path.abspath(__file__))
    statistics_dir = path + '/data/statistics/'
    if not os.path.isdir(statistics_dir):
        os.makedirs(statistics_dir)
    parser = argparse.ArgumentParser(description="Signal monitoring app")
    parser.add_argument("-i", "--interface", help="The interface to be monitored", type=str, required=True)
    parser.add_argument("-p", "--pingto", help="Define an address to ping after activating OLSR to test", type=str)
    args = parser.parse_args()
    pingto = None
    if args.pingto:
       pingto = args.pingto

    start_monitoring(args.interface, pingto, statistics_dir)


def start_monitoring(interface: str, pingto: str, path: str):
    print("time, signal")
    olsrd_running = False
    csv_columns = ['time', 'signal', 'signal avg', 'rx bitrate', 'tx bitrate', 'expected throughput']
    start_time = datetime.now()
    file = path + start_time.strftime('%Y-%m-%d_%H-%M-%S_') + interface + '_signal_quality.csv'
    time.sleep(1)
    subprocess.Popen(["ping", "-c1", "ap1"]).communicate()
    while True:
        data = get_signal_quality(interface)
        if data:
            data.update({'time': datetime.now().timestamp()})
            print("{}, {}".format(data['time'], data['signal']))
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
            reconnected = try_reconnect(interface, ssid="ap1-ssid", address="00:00:00:00:01:00")
            if not reconnected and not olsrd_running:
                start_olsrd(interface)
                olsrd_running = True
                if pingto:
                    subprocess.Popen(["ping", "-c1", pingto]).communicate()
        time.sleep(1)


def get_signal_quality(interface: str):
    stdout, stderr = cmd_iw_dev(interface, "station", "dump")
    data = stdout.decode()
    if "Station 00:00:00:00:01:00" in data:
        data = list(filter(None, data.split('\n\t')[1:]))
        data = dict(map(lambda s: s.split(':'), data))
        signal_data = {k: (data[k] if k in data else 'NaN') for k in ['signal', 'signal avg', 'rx bitrate',
                                                                      'tx bitrate', 'expected throughput']}
        return signal_data
    return None


def try_reconnect(interface: str, ssid: str, address: str):
    stdout, stderr = cmd_iw_dev(interface, "scan")
    data = stdout.decode()
    if "BSS " + address in data and "SSID: ap1-ssid" in data:
        stdout, stderr = cmd_iw_dev(interface, "connect", ssid)
        print(stdout)
        return True
    return False


def start_olsrd(interface: str):
    ibss = {'ssid': 'adhocNet', 'freq': '2432', 'ht_cap': 'HT40+', 'ibss': '02:CA:FF:EE:BA:01'}
    stdout, stderr = cmd_iw_dev(interface, "set", "type", "ibss")
    log.info("*** Set {} type to ibss".format(interface))
    stdout, stderr = cmd_ip_link_set(interface, "up")
    log.info("*** Set ip link {} up".format(interface))
    stdout, stderr = cmd_iw_dev(interface, "ibss", "join", ibss['ssid'], ibss['freq'], ibss['ht_cap'], ibss['ibss'])
    log.info("*** {}: Join ibss adhocNet".format(interface))
    time.sleep(1)
    # something does not work when starting OLSRD with this
    olsrd_process = subprocess.Popen(["olsrd", "-i", interface, "-d", "0"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in iter(olsrd_process.stdout.readline, b''):
        if b'detaching from the current process...' in line:
            break
    print(olsrd_process.args, olsrd_process.pid)
    # OLSRD starts with this one but it gets stuck somewhere after that, maybe open a new thread for this to prevent blocking...
    stdout, stderr = cmd("olsrd", "-i", interface, "-d", "0", shell=True)
    log.info("*** Start olsrd on {}\n".format(interface))
    # greping the PID works with this if the previous commands do not block...
    subprocess.Popen("ps all | grep 'olsrd -i {}' | grep -v grep".format(interface), shell=True).communicate()
    stdout, stderr = cmd("ps all | grep 'olsrd -i {}' | grep -v grep".format(interface), shell=True)
    log.info("*** Get olsrd pid: {}\n".format(stdout))


def stop_olsrd(interface: str, pid: int):
    cmd_iw_dev(interface, "ibss", "leave")
    cmd_iw_dev(interface, "set", "type", "managed")


def cmd(*args, **kwargs):
    stdout, stderr = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs).communicate()
    return stdout, stderr


def cmd_iw_dev(interface: str, cmd: str, *args):
    args = [arg for arg in args]
    stdout, stderr = subprocess.Popen(["iw", "dev", interface, cmd] + args, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE).communicate()
    return stdout, stderr


def cmd_ip_link_set(interface: str, state: str):
    stdout, stderr = subprocess.Popen(["ip", "link", "set", interface, state], stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE).communicate()
    return stdout, stderr


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
