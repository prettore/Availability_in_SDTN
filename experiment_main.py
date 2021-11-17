##################################################
## stript to create the network and setup the
# experiments
##################################################
## Author: Paulo H. L. Rettore
## Status: open
## Date: 01/10/2021
##################################################

import os
import random
import argparse
import subprocess
import pandas as pd
from time import sleep
from datetime import datetime
from mininet.term import makeTerm
from mininet.log import setLogLevel, info
from mininet.node import RemoteController, Controller, OVSKernelSwitch
from mn_wifi.link import wmediumd, mesh
from mn_wifi.cli import CLI
from mn_wifi.net import Mininet_wifi
from mn_wifi.wmediumdConnector import interference
from mn_wifi.replaying import ReplayingMobility

# changing the link rate based on node mobility using Qdisc
def network_change(station1, interface1, extra_arg, trace, trace_manet, buffer_size, exp_round, log_dir, event, manet):
    # adding TC and NetEm rule
    if not manet:  # using olsr
        makeTerm(station1, title='Changing the network - ' + interface1,
                 cmd="python change_link.py -i " + interface1 + " -qlen " + str(
                     buffer_size) + " " + extra_arg + " -t '" + trace + "' -t2 '" + trace_manet + "' -e " + log_dir + event)
    else:  # no olsr
        makeTerm(station1, title='Changing the network - ' + interface1,
                 cmd="python change_link.py -i " + interface1 + " -qlen " + str(
                     buffer_size) + " " + extra_arg + " -t '" + trace + "'")
        # print("python change_link.py -i " + interface1 + " -qlen " + str(
        #             buffer_size) + " " + extra_arg + " -t '" + trace + "'")
    sleep(2)
    if log_dir:
        # makeTerm(station1, title='Qdisc', cmd="python packet_queue.py -i "+interface1)
        makeTerm(station1, title='Qdisc',
                 cmd="python packet_queue.py -i " + interface1 + " -o " + log_dir + station1.name + "_buffer.csv" +
                     " -r " + str(exp_round) + " -qlen " + str(buffer_size))
        # print("python packet_queue.py -i "+interface1+" -o "+log_dir+station1.name + "_buffer.csv" +
        #                                                     " -r " + str(exp_round) + " -qlen " + str(buffer_size))

# creating packet sniffer
def packet_sniffer(station1, station2, interface1, interface2, exp_round):
    command = "sudo python packet_sniffer.py -i " + interface2 + " -o recv_packets.csv -r " + exp_round + " -f 'udp and port 8999'"
    makeTerm(station2, title='Monitoring IP packets at Receiver', cmd=command)

    command = "sudo python packet_sniffer.py -i " + interface1 + " -o send_packets.csv -r " + exp_round + " -f '-p udp -m udp --dport 8999' -T True"
    makeTerm(station1, title='Monitoring IP packets at Sender', cmd=command)

# creating user data flows
def user_data_flow(station1, station2, statistics_dir):
    # Receiver
    # reference: http://traffic.comics.unina.it/software/ITG/manual/index.html
    makeTerm(station2, title='Server',
             cmd="ITGRecv -Si sta3-eth2 -Sp 9090 -a 10.0.0.3 -i sta3-wlan0 -l {}/receiver.log".format(statistics_dir))

    sleep(10)

    if scenario == 1:
        # experiment 10 min Pendulum
        makeTerm(station1, title='Client',
                 cmd="ITGSend -Sda 192.168.0.3 -Sdp 9090 -T UDP -a 10.0.0.3 -U 2 30 -z 2500 -s 0.123456 -c 1264000 -t "
                     "10000000 -l {}/sender.log -c 1000".format(statistics_dir))  # uhf
        # makeTerm(station1, title='Client',
        #          cmd="ITGSend -Sda 192.168.0.3 -Sdp 9090 -T UDP -a 10.0.0.3 -U 2 30 -z 2500 -s 0.123456 -c 1264 -t "
        #              "10000000 -l {}/sender.log -c 1000".format(statistics_dir))  # uhf
    if scenario == 2:
        # long experiment 30 min GM
        makeTerm(station1, title='Client',
                 cmd="ITGSend -Sda 192.168.0.3 -Sdp 9090 -T UDP -a 10.0.0.3 -U 2 20 -z 6000 -s 0.123456 -c 1264 -t 10000000 "
                     "-l {}/sender.log -c 1000".format(statistics_dir))  # uhf

# reading trace files
def get_trace(sta_list, file_, smooth, addrand):
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
            if addrand:  # in case the nodes are at the same location
                x = row['x'] + random.randint(-10, 10)
                y = row['y'] + random.randint(-10, 10)
            else:
                x = row['x']
                y = row['y']
            t = row['time']
            if smooth:
                sta_list[n].coord.append(str(x) + "," + str(y) + ",0.0")
            pos = float(x), float(y), 0.0
            sta_list[n].p.append(pos)
            sta_list[n].time.append(t)


def topology(scenario: int, signal_window: int, scan_interval: float, disconnect_threshold: float,
             reconnect_threshold: float, bufferSize, scan_iface: bool = False, no_olsr: bool = False,
             auto: bool = False):
    """
    Build a custom topology and start it.

    Note: If you do not want to use a remote SDN controller but the controller class that is included in Mininet-Wifi you will have to change some
    """
    net = Mininet_wifi(topo=None, build=False, link=wmediumd, wmediumd_mode=interference, noise_th=-91,
                       fading_cof=3, allAutoAssociation=True)

    info('*** Adding controller\n')
    # Use this if you have a remote controller (e.g. RYU controller) installed and running in the background
    # c0 = net.addController(name='c0', controller=RemoteController, ip='127.0.0.1', port=6633)

    # Use this instead if you want to use the SDN controller provided by Mininet-Wifi
    c0 = net.addController(name='c0', controller=Controller)

    info('*** Adding switches/APs\n')
    # Use this SDN switch configuration if you use the RYU controller as a remote controller
    ap1 = net.addAccessPoint('ap1', ip='10.0.0.10', mac='00:00:00:00:01:00', listenPort=6634, dpid='0000000000000010',
                             ssid='ap1-ssid', mode='g', channel='1', position='30,50,0')
    s1 = net.addSwitch('s1', cls=OVSKernelSwitch, failMode='standalone')

    # Use this if you are using the SDN controller provided by Mininet-Wifi
    # ap1 = net.addAccessPoint('ap1', ip='10.0.0.10', mac='00:00:00:00:01:00', ssid='ap1-ssid', mode='g', channel='1', position='30,50,0')

    info("*** Creating nodes\n")
    if scan_iface:
        scanif = 1
        sta1 = net.addStation('sta1', wlans=2, ip='10.0.0.1', position='30,10,0', color='r')
        sta3 = net.addStation('sta3', wlans=2, ip='10.0.0.3', position='50,40,0', color='b')
    else:
        scanif = 0
        sta1 = net.addStation('sta1', mac='00:00:00:00:00:01', ip='10.0.0.1', position='30,10,0', color='r')
        sta3 = net.addStation('sta3', mac='00:00:00:00:00:03', ip='10.0.0.3', position='50,40,0', color='b')

    info("*** Configuring propagation model\n")
    net.setPropagationModel(model="logDistance", exp=2.257)  # around 2000meters range uhf
    # net.setPropagationModel(model="logDistance", exp=3.8)  # around 100meters range wifi

    info("*** Configuring wifi nodes\n")
    net.configureWifiNodes()

    info("*** Creating wired links\n")
    net.addLink(sta1, s1)  # ,intf='sta1-eth1')#,params1={'ip':'192.168.1.1/24'})#, link='wired')
    net.addLink(sta3, s1)  # ,intf='sta2-eth1')#,params1={'ip':'192.168.1.1/24'})#, link='wired')
    sta1.setIP('192.168.0.1/24', intf='sta1-eth2')
    sta3.setIP('192.168.0.3/24', intf='sta3-eth2')
    sta1.setMAC('00:00:00:00:00:04', intf='sta1-eth2')
    sta3.setMAC('00:00:00:00:00:05', intf='sta3-eth2')

    trace_file = ""
    info("*** Configuring mobility\n")
    if scenario == 1:
        trace_file = 'Trace_Pendulum_Filled_Shortest_NtoBS_UHF.csv'
        trace_manet_file = 'Trace_Pendulum_Filled_Shortest_NtoN_UHF.csv'  # used to change qdisc once the nodes are in a MANET mode
        smooth_motion = False
        path = os.path.dirname(os.path.abspath(__file__)) + '/data/'
        get_trace([sta1, sta3, ap1], path + trace_file, smooth_motion, False)
        net.isReplaying = True
        info("*** Creating plot\n")
        net.plotGraph(max_x=5000, max_y=6000)
    if scenario == 2:
        trace_file = 'Trace_GaussMarkov2_NtoBS_UHF.csv'
        trace_manet_file = 'Trace_GaussMarkov2_NtoN_UHF.csv'
        smooth_motion = False
        path = os.path.dirname(os.path.abspath(__file__)) + '/data/'
        get_trace([sta1, sta3, ap1], path + trace_file, smooth_motion, True)
        net.isReplaying = True
        info("*** Creating plot\n")
        net.plotGraph(max_x=3500, max_y=3500)

    info("*** Starting network\n")
    net.build()
    c0.start()
    net.get('ap1').start([c0])
    net.get('s1').start([c0])
    sleep(1)

    info("\n*** Replaying Mobility\n")
    ReplayingMobility(net)

    experiment_time = int(sta1.time[len(sta1.time) - 1])

    # makeTerm(sta1, title='Radio Buffer (Qdisc)', cmd="watch tc -s -j qdisc show dev sta1-wlan0")

    start_time = datetime.now()
    info("*** Starting flexible SDN script (time: {})\n".format(start_time.timestamp()))
    path = os.path.dirname(os.path.abspath(__file__))
    stat_dir = start_time.strftime('%Y-%m-%d_%H-%M-%S') + "/"
    statistics_dir = path + '/data/statistics/' + stat_dir
    if not os.path.isdir(statistics_dir):
        os.makedirs(statistics_dir)

    cmd = "sudo python"
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
    makeTerm(sta1, title='Station 1', cmd=cmd + " ; sleep 5")

    cmd = "sudo python"
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
    makeTerm(sta3, title='Station 3', cmd=cmd + " ; sleep 5")

    info("*** Changing the link rate based on node mobility\n")
    # changing the link rate based on node mobility
    network_change(sta1, 'sta1-wlan0', '-latency 2000 -dest 10.0.0.3 -src 10.0.0.1',
                   trace=trace_file, trace_manet=trace_manet_file, buffer_size=bufferSize, exp_round=0,
                   log_dir=statistics_dir, event="sta1_events.csv", manet=no_olsr)
    # network_change(sta3, 'sta3-wlan0', '-latency 2000 -dest 10.0.0.1/8 -src 10.0.0.3/8',
    #               trace=trace_file, trace_manet=trace_manet_file, buffer_size=100, exp_round=0,
    #               log_dir=False, event="sta3_events.csv",manet=no_olsr)

    # cmd = "python3 {}/packet_sniffer.py -i sta1-wlan0 -o {}send_packets.csv -f 'icmp[icmptype] = icmp-echo'".format(path, stat_dir)
    # cmd = "python3 {}/packet_sniffer.py -i sta1-wlan0 -o {}send_packets.csv -f '-p udp -m udp --dport 8999' -T True".format(path, stat_dir)
    # makeTerm(sta1, title='Packet Sniffer sta1', cmd=cmd + " ; sleep 10")
    # cmd = "python3 {}/packet_sniffer.py -i sta3-wlan0 -o {}recv_packets.csv -f 'icmp[icmptype] = icmp-echo'".format(path, stat_dir)
    # cmd = "python3 {}/packet_sniffer.py -i sta3-wlan0 -o {}recv_packets.csv -f 'udp dst port 8999'".format(path, stat_dir)
    # makeTerm(sta3, title='Packet Sniffer sta3', cmd=cmd + " ; sleep 10")
    # packet_sniffer(sta1, sta3, 'sta1-wlan0' ,'sta3-wlan0', trace_file, 0)

    sleep(2)
    # info("*** Starting ping: sta1 (10.0.0.1) -> sta3 (10.0.0.3)\n")
    # makeTerm(sta1, title='ping', cmd="ping 10.0.0.3")
    info("*** Start sending generated packets: sta1 (10.0.0.1) -> sta3 (10.0.0.3)\n")
    # makeTerm(sta3, title='Recv', cmd="ITGRecv -a 10.0.0.3 -i sta3-wlan0 -l {}/receiver.log".format(statistics_dir))
    # makeTerm(sta1, title='Send', cmd="ITGSend -T UDP -C 10 -a 10.0.0.3 -c 1264 -s 0.123456 -t 600000 -l {}/sender.log -c 1000 ; sleep 10".format(statistics_dir))
    user_data_flow(sta1, sta3, statistics_dir)

    print(auto)

    if auto:
        info("*** Experiment duration - " + str(experiment_time + 20) + " seconds \n")
        sleep(experiment_time + 20)
        queue_has_packet = True
        while queue_has_packet:
            with open(statistics_dir + 'sta1_packet_queue.txt', 'r') as file:
                line = file.readline()
                if line != 'True':
                    queue_has_packet = False
                else:
                    sleep(10)
        info("*** Stopping network\n")
        os.system('sudo pkill xterm')
        net.stop()

        out, err = subprocess.Popen(['pgrep', 'olsrd'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        if out:
            subprocess.Popen(['killall', 'olsrd'])
        subprocess.Popen(["python3", "{}/eval_ditg.py".format(path), "-d", statistics_dir, "-t",
                          str(start_time.timestamp())]).communicate()
        if no_olsr:
            plot_cmd = ["python3", "{}/plot_statistics_new.py".format(path), "-d", statistics_dir, '-O', '-f', trace_file]
        else:
            plot_cmd = ["python3", "{}/plot_statistics_new.py".format(path), "-d", statistics_dir, '-f', trace_file]
        subprocess.Popen(plot_cmd).communicate()
        os.system("chown -R wifi {}".format(path + '/data/statistics/'))
    else:
        info("*** Running CLI\n")
        CLI(net)
        info("*** Stopping network\n")
        os.system('sudo pkill xterm')
        net.stop()
        out, err = subprocess.Popen(['pgrep', 'olsrd'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        if out:
            subprocess.Popen(['killall', 'olsrd'])
        subprocess.Popen(["python3", "{}/eval_ditg.py".format(path), "-d", statistics_dir, "-t",
                          str(start_time.timestamp())]).communicate()
        if no_olsr:
            plot_cmd = ["python3", "{}/plot_statistics_new.py".format(path), "-d", statistics_dir, '-O', '-f', trace_file]
        else:
            plot_cmd = ["python3", "{}/plot_statistics_new.py".format(path), "-d", statistics_dir, '-f', trace_file]
        subprocess.Popen(plot_cmd).communicate()
        os.system("chown -R wifi {}".format(path + '/data/statistics/'))




if __name__ == '__main__':
    setLogLevel('info')
    parser = argparse.ArgumentParser(description="Tactical network experiment!")
    parser.add_argument("-m", "--mobilityScenario",
                        help="Select a mobility scenario (Integer: 1 or 2) (default: 1)"
                             " where 1: Pendulum (UHF), 2: GaussMarkov (UHF)",
                        type=int, required=False, default=1)
    parser.add_argument("-s", "--scanInterval", help="Time interval in seconds (float) for scanning if the wifi CP"
                                                     " is in range while being in adhoc mode (default: 2.0)",
                        type=float, default=2.0)
    parser.add_argument("-d", "--disconnectThreshold", help="Signal strength (float) below which station disconnects "
                                                            "from CP and activates OLSR (default: -87.0 dBm)",
                        type=float, default=-87.0)
    parser.add_argument("-r", "--reconnectThreshold", help="Minimal signal strength (float) of CP required for trying "
                                                           "reconnect (default: -82.0 dBm)", type=float, default=-82.0)
    parser.add_argument("-S", "--scanInterface", help="Use a second interface for scanning to prevent blocking the "
                                                      "primary interface and thus disrupting the data flow (default: "
                                                      "True)", action="store_true", default=True)
    parser.add_argument("-w", "--signalWindow", help="Window for the moving average calculation of the CP signal "
                                                     "strength (default: 10)", type=int, default=10)
    parser.add_argument("-O", "--noOlsr", help="Set to disable the usage of olsr when connection to CP is lost "
                                               "(default: False)", action='store_true', default=False)
    parser.add_argument("-b", "--bufferSize", help="Set the node buffer size (default: 100 packets)",
                        type=int, required=False, default=100)

    parser.add_argument("-auto", "--auto", help="Automatically stop the experiment after the buffer is empty",
                        action='store_true', required=False, default=False)

    args = parser.parse_args()
    scenario = args.mobilityScenario
    topology(scenario, args.signalWindow, args.scanInterval, args.disconnectThreshold, args.reconnectThreshold,
             args.bufferSize, args.scanInterface, args.noOlsr, args.auto)
