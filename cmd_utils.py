import subprocess

from subprocess import PIPE


def cmd(*args, **kwargs):
    """
    Executes the given command with given args as a subprocess.
    Returns output and errors of the subprocess after it has terminated.
    """
    stdout, stderr = subprocess.Popen(args, stdout=PIPE, stderr=PIPE, **kwargs).communicate()
    return stdout, stderr


def cmd_iw_dev(interface: str, cmd: str, *args):
    """
    Executes iw dev with given args including the interface in a subprocess.
    Returns output and errors of the subprocess after it has terminated.
    """
    args = [arg for arg in args]
    stdout, stderr = subprocess.Popen(["iw", "dev", interface, cmd] + args, stdout=PIPE, stderr=PIPE).communicate()
    return stdout, stderr


def cmd_ip_link_set(interface: str, *args):
    """
    Executes sets the link state of a given interface to a given state by executing the ip command in a subprocess.
    Returns output and errors of the subprocess after it has terminated.
    """
    args = [arg for arg in args]
    stdout, stderr = subprocess.Popen(["ip", "link", "set", interface] + args, stdout=PIPE, stderr=PIPE).communicate()
    return stdout, stderr


def cmd_ip_link_show(interface: str):
    stdout, stderr = subprocess.Popen(["ip", "link", "show", interface], stdout=PIPE, stderr=PIPE).communicate()
    return stdout, stderr
