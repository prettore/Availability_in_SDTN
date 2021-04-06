import logging
import multiprocessing
import os
import csv

from time import sleep
from datetime import datetime
from cmd_utils import cmd_iw_dev

log = logging.getLogger('logger')


class Scanner(multiprocessing.Process):
    def __init__(self, interface: str, interval: float, log_path: str, station: str, ctrl_start_time: float,
                 ssid: str = None):
        super().__init__()
        self.interface = interface
        self.interval = interval
        self.ssid = ssid
        self.log_file = log_path + station + '_events.csv'
        self.control_start_time = ctrl_start_time

    def run(self):
        log.info(
            "*** {}: Scanner started. Searching for {} with interval {}".format(
                self.interface, self.ssid, self.interval))
        while True:
            sleep(self.interval)
            log.info("*** {}: Scanning for {}".format(self.interface, self.ssid))
            self.log_event('scan_trigger')
            if self.ssid:
                stdout, stderr = cmd_iw_dev(self.interface, "scan", "ssid", self.ssid)
            else:
                stdout, stderr = cmd_iw_dev(self.interface, "scan")

    def log_event(self, event: str):
        csv_columns = ['time', 'disconnect', 'reconnect', 'scanner_start', 'scanner_stop', 'scan_trigger']
        data = {k: 0 for k in csv_columns}
        data.update({'time': datetime.now().timestamp() - self.control_start_time, event: 1})
        self.write_or_append_csv_to_file(data, csv_columns)

    def write_or_append_csv_to_file(self, data: dict, csv_columns: list):
        if os.path.isfile(self.log_file):
            with open(self.log_file, 'a') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
                writer.writerow(data)
        else:
            with open(self.log_file, 'w') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
                writer.writeheader()
                writer.writerow(data)
