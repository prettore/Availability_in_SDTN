import os
import argparse
import subprocess
import pandas as pd
from time import sleep
from datetime import datetime

from mininet.term import makeTerm
from mininet.log import setLogLevel, info
from mininet.node import RemoteController, Controller
from mn_wifi.link import wmediumd, mesh
from mn_wifi.cli import CLI
from mn_wifi.net import Mininet_wifi
from mn_wifi.wmediumdConnector import interference
from mn_wifi.replaying import ReplayingMobility


def topology(scenario: int, signal_window: int, scan_interval: float, disconnect_threshold: float,
             reconnect_threshold: float, scan_iface: bool = False, no_olsr: bool = False,
             qdisc_rates: dict = {'disconnect': 0, 'reconnect': 0}):
    """
    Build a custom topology and start it.

    Note: If you do not want to use a remote SDN controller but the controller class that is included in Mininet-Wifi you will have to change some
    """
    net = Mininet_wifi(topo=None, build=False, link=wmediumd, wmediumd_mode=interference, noise_th=-91, fading_cof=3,
                       autoAssociation=False, allAutoAssociation=False)

    info('*** Adding controller\n')
    # Use this if you have a remote controller (e.g. RYU controller) intalled and running in the background
    c0 = net.addController(name='c0', controller=RemoteController, ip='127.0.0.1', port=6633)

    # Use this instead if you want to use the SDN controller provided by Mininet-Wifi
    # c0 = net.addController(name='c0', controller=Controller)

    info('*** Adding switches/APs\n')
    # Use this SDN switch configuration if you use the RYU controller as a remote controller
    ap1 = net.addAccessPoint('ap1', ip='10.0.0.10', mac='00:00:00:00:01:00', listenPort=6634, dpid='0000000000000010',
                             ssid='ap1-ssid', mode='g', channel='1', position='30,50,0')

    # Use this if you are using the SDN controller provided by Mininet-Wifi
    # ap1 = net.addAccessPoint('ap1', ip='10.0.0.10', mac='00:00:00:00:01:00', ssid='ap1-ssid', mode='g', channel='1', position='30,50,0')

    info("*** Creating nodes\n")
    if scan_iface:
        scanif = 1
        sta1 = net.addStation('sta1', wlans=2, ip='10.0.0.1', position='30,10,0')
        sta2 = net.addStation('sta2', wlans=2, ip='10.0.0.2', position='10,40,0')
        sta3 = net.addStation('sta3', wlans=2, ip='10.0.0.3', position='50,40,0')
    else:
        scanif = 0
        sta1 = net.addStation('sta1', mac='00:00:00:00:00:01', ip='10.0.0.1', position='30,10,0')
        sta2 = net.addStation('sta2', mac='00:00:00:00:00:02', ip='10.0.0.2', position='10,40,0')
        sta3 = net.addStation('sta3', mac='00:00:00:00:00:03', ip='10.0.0.3', position='50,40,0')

    info("*** Configuring propagation model\n")
    net.setPropagationModel(model="logDistance", exp=4.4)

    info("*** Configuring wifi nodes\n")
    net.configureWifiNodes()

    if scenario > 1:
        info("*** Configuring moblity\n")
        if scenario == 2:
            trace_file = 'Scenario_2.csv'
            smooth_motion = False
            path = os.path.dirname(os.path.abspath(__file__)) + '/data/'
            get_trace([sta1, sta2, sta3], path + trace_file, smooth_motion)
            net.isReplaying = True
        if scenario == 3:
            trace_file = 'Scenario_3.csv'
            smooth_motion = False
            path = os.path.dirname(os.path.abspath(__file__)) + '/data/'
            get_trace([sta1, sta2, sta3], path + trace_file, smooth_motion)
            net.isReplaying = True
        if scenario == 4:
            trace_file = 'Scenario_1.csv'
            smooth_motion = False
            path = os.path.dirname(os.path.abspath(__file__)) + '/data/'
            get_trace([sta1, sta2, sta3], path + trace_file, smooth_motion)
            net.isReplaying = True

    info("*** Creating plot\n")
    net.plotGraph(max_x=100, max_y=100)

    info("*** Starting network\n")
    net.build()
    c0.start()
    net.get('ap1').start([c0])
    sleep(1)
    if scenario > 1:
        info("\n*** Replaying Mobility\n")
        ReplayingMobility(net)
    start_time = datetime.now()
    info("*** Starting flexible SDN script (time: {})\n".format(start_time.timestamp()))
    path = os.path.dirname(os.path.abspath(__file__))
    stat_dir = start_time.strftime('%Y-%m-%d_%H-%M-%S') + "/"
    statistics_dir = path + '/data/statistics/' + stat_dir
    if not os.path.isdir(statistics_dir):
        os.makedirs(statistics_dir)
    cmd = "python3"
    cmd += " {}/flexible_sdn.py".format(path)
    cmd += " -i sta1-wlan0"
    cmd += " -s {}".format(scan_interval)
    cmd += " -d {}".format(disconnect_threshold)
    cmd += " -r {}".format(reconnect_threshold)
    cmd += " -o {}".format(stat_dir)
    cmd += " -w {}".format(signal_window)
    cmd += " -t {}".format(start_time.timestamp())
    if scan_iface:
        cmd += " -S sta1-wlan1"
    if no_olsr:
        cmd += " -O"
    if qdisc_rates['disconnect'] > 0 and qdisc_rates['reconnect'] > 0:
        cmd += " -qr {} -qd {}".format(qdisc_rates['reconnect'], qdisc_rates['disconnect'])
    makeTerm(sta1, title='Station 1', cmd=cmd + " ; sleep 10")
    cmd = "python3"
    cmd += " {}/flexible_sdn.py".format(path)
    cmd += " -i sta3-wlan0"
    cmd += " -s {}".format(scan_interval)
    cmd += " -d {}".format(disconnect_threshold)
    cmd += " -r {}".format(reconnect_threshold)
    cmd += " -o {}".format(stat_dir)
    cmd += " -w {}".format(signal_window)
    cmd += " -t {}".format(start_time.timestamp())
    if scan_iface:
        cmd += " -S sta3-wlan1"
    if no_olsr:
        cmd += " -O"
    if qdisc_rates['disconnect'] > 0 and qdisc_rates['reconnect'] > 0:
        cmd += " -qr {} -qd {}".format(qdisc_rates['reconnect'], qdisc_rates['disconnect'])
    makeTerm(sta3, title='Station 3', cmd=cmd + " ; sleep 10")
    # cmd = "python3 {}/packet_sniffer.py -i sta1-wlan0 -o {}send_packets.csv -f 'icmp[icmptype] = icmp-echo'".format(path, stat_dir)
    # cmd = "python3 {}/packet_sniffer.py -i sta1-wlan0 -o {}send_packets.csv -f '-p udp -m udp --dport 8999' -T True".format(path, stat_dir)
    # makeTerm(sta1, title='Packet Sniffer sta1', cmd=cmd + " ; sleep 10")
    # cmd = "python3 {}/packet_sniffer.py -i sta3-wlan0 -o {}recv_packets.csv -f 'icmp[icmptype] = icmp-echo'".format(path, stat_dir)
    # cmd = "python3 {}/packet_sniffer.py -i sta3-wlan0 -o {}recv_packets.csv -f 'udp dst port 8999'".format(path, stat_dir)
    # makeTerm(sta3, title='Packet Sniffer sta3', cmd=cmd + " ; sleep 10")
    sleep(2)
    # info("*** Starting ping: sta1 (10.0.0.1) -> sta3 (10.0.0.3)\n")
    # makeTerm(sta1, title='ping', cmd="ping 10.0.0.3")
    info("*** Start sending generated packets: sta1 (10.0.0.1) -> sta3 (10.0.0.3)\n")
    makeTerm(sta3, title='Recv', cmd="ITGRecv -a 10.0.0.3 -i sta3-wlan0 -l {}/receiver.log".format(statistics_dir))
    makeTerm(sta1, title='Send', cmd="ITGSend -T UDP -C 10 -a 10.0.0.3 -c 1264 -s 0.123456 -t 170000 -l {}/sender.log ; sleep 10".format(statistics_dir))
    info("\n*** Running CLI\n")
    CLI(net)
    net.stop()
    os.system('sudo pkill xterm')
    out, err = subprocess.Popen(['pgrep', 'olsrd'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    if out:
        subprocess.Popen(['killall', 'olsrd'])
    subprocess.Popen(["python3", "{}/eval_ditg.py".format(path), "-d", statistics_dir, "-t", str(start_time.timestamp())]).communicate()
    if no_olsr:
        plot_cmd = ["python3", "{}/plot_statistics.py".format(path), "-d", statistics_dir, '-O']
    else:
        plot_cmd = ["python3", "{}/plot_statistics.py".format(path), "-d", statistics_dir]
    subprocess.Popen(plot_cmd).communicate()
    os.system("chown -R wifi {}".format(path + '/data/statistics/'))


def get_trace(sta_list, file_, smooth):
    """Read a trace file"""
    df_trace = pd.read_csv(file_)
    df_trace['node'] = df_trace['node'].astype(int)
    trace_node = df_trace.groupby('node')

    for n in trace_node.groups:
        sta_list[n].time = []
        sta_list[n].p = []
        if smooth:
            sta_list[n].coord = []
        trace = trace_node.get_group(n)
        # for row in trace:
        for index, row in trace.iterrows():
            x = row['x']
            y = row['y']
            t = row['time']
            if smooth:
                sta_list[n].coord.append(str(x) + "," + str(y) + ",0.0")
            pos = float(x), float(y), 0.0
            sta_list[n].p.append(pos)
            sta_list[n].time.append(t)


if __name__ == '__main__':
    setLogLevel('info')
    parser = argparse.ArgumentParser(description="Tactical network experiment!")
    parser.add_argument("-m", "--mobilityscenario", help="Select a mobility scenario (Integer: 1, 2 or 3) (default: 1)",
                        type=int, required=True, default=1)
    parser.add_argument("-s", "--scaninterval", help="Time interval in seconds (float) for scanning if the wifi access "
                                                     "point is in range while being in adhoc mode (default: 10.0)",
                        type=float, default=5.0)
    parser.add_argument("-d", "--disconnectthreshold", help="Signal strength (float) below which station dissconnects "
                                                            "from AP and activates OLSR (default: -70.0 dBm)",
                        type=float, default=-70.0)
    parser.add_argument("-r", "--reconnectthreshold", help="Minimal signal strength (float) of AP required for trying "
                                                           "reconnect (default: -65.0 dBm)", type=float, default=-65.0)
    parser.add_argument("-S", "--scaninterface", help="Use a second interface for scanning to prevent blocking the "
                                                      "primary interface and thus disrupting the data flow (default: True)",
                        action="store_true",
                        default=True)
    parser.add_argument("-w", "--signalwindow", help="Window for the moving average calculation of the AP signal "
                                                     "strength (default: 3)",
                        type=int, default=3)
    parser.add_argument("-O", "--noolsr", help="Set to disable the usage of olsr when connection to AP is lost "
                                               "(default: False)", action='store_true', default=False)
    parser.add_argument("-qd", "--qdiscdisconnect", help="Bandwidth in bits/s to throttle qdisc to during handover AP "
                                                         "to OLSR. If set to 0 qdisc feature is deactivated "
                                                         "(default: 0)", type=int, default=0)
    parser.add_argument("-qr", "--qdiscreconnect", help="Bandwidth in bits/s to throttle qdisc to during handover AP to"
                                                        " OLSR. If set to 0 qdisc feature is deactivated (default: 0)",
                        type=int, default=0)
    args = parser.parse_args()
    scenario = args.mobilityscenario
    qdisc_rates = {'disconnect': args.qdiscdisconnect, 'reconnect': args.qdiscreconnect}
    topology(scenario, args.signalwindow, args.scaninterval, args.disconnectthreshold, args.reconnectthreshold,
             args.scaninterface, args.noolsr, qdisc_rates)
