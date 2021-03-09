import os
import argparse
import subprocess
import time
import csv

from datetime import datetime


def main():
    path = os.path.dirname(os.path.abspath(__file__))
    statistics_dir = path + '/data/statistics/'
    if not os.path.isdir(statistics_dir):
        os.makedirs(statistics_dir)
    parser = argparse.ArgumentParser(description="Signal monitoring app")
    parser.add_argument("-i", "--interface", help="The interface to be monitored", type=str, required=True)
    args = parser.parse_args()

    start_monitoring(args.interface, statistics_dir)


def start_monitoring(interface: str, path: str):
    print("time, signal")
    csv_columns = ['time', 'signal', 'signal avg', 'rx bitrate', 'tx bitrate', 'expected throughput']
    start_time = datetime.now()
    file = path + start_time.strftime('%Y-%m-%d_%H-%M-%S_') + interface + '_signal_quality.csv'
    subprocess.Popen(["ping", "-c1", "10.0.0.10"]).communicate()
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
            # print('signal:', data)
            time.sleep(1)


def get_signal_quality(interface: str):
    stdout, stderr = subprocess.Popen(["iw", "dev", interface, "station", "dump"], stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE).communicate()
    data = stdout.decode()
    if "Station 00:00:00:00:01:00" in data:
        data = list(filter(None, data.split('\n\t')[1:]))
        data = dict(map(lambda s: s.split(':'), data))
        signal_data = {k: (data[k] if k in data else 'NaN') for k in ['signal', 'signal avg', 'rx bitrate',
                                                                      'tx bitrate', 'expected throughput']}
        return signal_data
    return None


if __name__ == '__main__':
    main()
