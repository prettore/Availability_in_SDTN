import logging
import multiprocessing

from time import sleep
from cmd_utils import cmd_iw_dev

log = logging.getLogger('logger')


class Scanner(multiprocessing.Process):
    def __init__(self, interface: str, interval: float, ssid: str = None):
        super().__init__()
        self.interface = interface
        self.interval = interval
        self.ssid = ssid

    def run(self):
        while True:
            sleep(self.interval)
            log.info("*** {}: Scanning for {}".format(self.interface, self.ssid))
            if self.ssid:
                stdout, stderr = cmd_iw_dev(self.interface, "scan", "ssid", self.ssid)
            else:
                stdout, stderr = cmd_iw_dev(self.interface, "scan")
