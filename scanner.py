import multiprocessing

from time import sleep
from cmd_utils import cmd_iw_dev


class Scanner(multiprocessing.Process):
    def __init__(self, interface: str, interval: float, ssid: str = None):
        super().__init__()
        self.interface = interface
        self.interval = interval
        self.ssid = ssid

    def run(self):
        sleep(2)
        while True:
            if self.ssid:
                stdout, stderr = cmd_iw_dev(self.interface, "scan", "ssid", self.ssid)
            else:
                stdout, stderr = cmd_iw_dev(self.interface, "scan")
            sleep(self.interval)
