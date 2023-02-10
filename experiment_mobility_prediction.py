import os
import argparse
import socket
import subprocess
from datetime import datetime
from typing import Tuple

import pandas as pd
from time import sleep

from mn_wifi.cli import CLI
from mn_wifi.net import Mininet_wifi
from mininet.term import makeTerm
from mininet.log import setLogLevel, info
from mn_wifi.link import wmediumd, mesh
from mn_wifi.wmediumdConnector import interference
from mininet.node import RemoteController, Controller, OVSKernelSwitch
from mn_wifi.telemetry import telemetry

from trace_reader import TraceReaderMobilityPrediction
from preprocessing_traces_mobility_prediction import get_coord_min_max

# Can be executed for testing and debugging in the mininet wifi VM with:
# sudo python3 experiment_mobility_prediction.py -m GaussMarkov -p 5 --auto


def main(scenario: str, prediction_interval: int, disconnect_state: int, reconnect_state: int, handover_delay: float,
         buffer_size, auto: bool = False):
    net = Mininet_wifi(topo=None, build=False, link=wmediumd, wmediumd_mode=interference, noise_th=-91,
                       fading_cof=3, allAutoAssociation=True)

    info('*** Adding controller\n')
    # Use this if you have a remote controller (e.g. RYU controller) installed and running in the background
    # c0 = net.addController(name='c0', controller=RemoteController, ip='127.0.0.1', port=6633)

    # Use this instead if you want to use the SDN controller provided by Mininet-Wifi
    c0 = net.addController(name='c0', controller=Controller)

    info('*** Adding switches/APs\n')
    ap_position, sta1_pos, sta3_pos = get_init_positions(scenario, prediction_interval)
    info(f"*** Placing AP at position: {ap_position}\n")
    # Use this SDN switch configuration if you use the RYU controller as a remote controller
    ap1 = net.addAccessPoint('ap1', ip='10.0.0.10', mac='00:00:00:00:01:00', listenPort=6634, dpid='0000000000000010',
                             ssid='ap1-ssid', mode='g', channel='1', position=ap_position)
    # s1 = net.addSwitch('s1', cls=OVSKernelSwitch, failMode='standalone')

    # Use this if you are using the SDN controller provided by Mininet-Wifi
    # ap1 = net.addAccessPoint('ap1', ip='10.0.0.10', mac='00:00:00:00:01:00', ssid='ap1-ssid', mode='g', channel='1', position='30,50,0')

    info("*** Creating nodes\n")
    sta1 = net.addStation('sta1', mac='00:00:00:00:00:01', ip='10.0.0.1', position=sta1_pos, color='r')
    sta3 = net.addStation('sta3', mac='00:00:00:00:00:03', ip='10.0.0.3', position=sta3_pos, color='b')

    info("*** Configuring propagation model\n")
    net.setPropagationModel(model="logDistance", exp=2.257)  # around 2000meters range uhf
    # net.setPropagationModel(model="logDistance", exp=3.8)  # around 100meters range wifi

    info("*** Configuring wifi nodes\n")
    net.configureWifiNodes()

    info("*** Creating wired links\n")
    net.addLink(sta1, ap1)  # ,intf='sta1-eth1')#,params1={'ip':'192.168.1.1/24'})#, link='wired')
    net.addLink(sta3, ap1)  # ,intf='sta2-eth1')#,params1={'ip':'192.168.1.1/24'})#, link='wired')
    # FIXME setting IPs fails because the referenced interfaces do not exist
    # sta1.setIP('192.168.0.1/24', intf='sta1-eth2')
    # sta3.setIP('192.168.0.3/24', intf='sta3-eth2')
    # sta1.setMAC('00:00:00:00:00:04', intf='sta1-eth2')
    # sta3.setMAC('00:00:00:00:00:05', intf='sta3-eth2')

    info("*** Configuring mobility\n")
    df_trace_sta1 = get_trace(scenario, "sta1", prediction_interval)
    df_trace_sta3 = get_trace(scenario, "sta3", prediction_interval)
    net.isReplaying = True

    info("*** Preparing logs\n")
    start_time = datetime.now()
    path = os.path.dirname(os.path.abspath(__file__))
    stat_dir = start_time.strftime('%Y-%m-%d_%H-%M-%S') + "/"
    statistics_dir = path + '/data/statistics/' + stat_dir
    if not os.path.isdir(statistics_dir):
        os.makedirs(statistics_dir)

    info("*** Creating plot\n")
    # FIXME plot does not work
    _, x_max_1, _, y_max_1 = get_coord_min_max(df_trace_sta1)
    _, x_max_3, _, y_max_3 = get_coord_min_max(df_trace_sta3)
    info(f"*** Plot size: max(x)={max(x_max_1, x_max_3) + 100} max(y)={max(y_max_1, y_max_3) + 100}\n")
    # net.plotGraph(max_x=100, max_y=100)

    info("*** Starting network\n")
    net.build()
    c0.start()
    net.get('ap1').start([c0])
    # net.get('s1').start([c0])
    sleep(1)

    nodes = net.stations
    info(f"{type(nodes)}\n{nodes}\n")
    telemetry(nodes=nodes, data_type='position', min_x=0, min_y=0,
              max_x=max(x_max_1, x_max_3) + 100, max_y=max(y_max_1, y_max_3) + 100)

    host = "10.0.2.15"
    port = 12345
    info(f"*** Starting Socket Server: {host}:{port}\n")
    net.socketServer(ip=host, port=port)

    cmd = f"sudo python {path}/flexible_sdn_mobility_prediction.py"
    cmd += " -i sta1-wlan0"
    cmd += f" -s {statistics_dir}"
    cmd += f" -t {start_time.timestamp()}"
    cmd += f" -f {path}/data/{scenario}/{scenario}_sta1_{prediction_interval}-sec_pred-results_pp.csv"
    makeTerm(sta1, title="Station 1", cmd=cmd + " ; sleep 60")

    cmd = f"sudo python {path}/flexible_sdn_mobility_prediction.py"
    cmd += " -i sta3-wlan0"
    cmd += f" -s {statistics_dir}"
    cmd += f" -t {start_time.timestamp()}"
    cmd += f" -f {path}/data/{scenario}/{scenario}_sta3_{prediction_interval}-sec_pred-results_pp.csv"
    makeTerm(sta3, title="Station 3", cmd=cmd + " ; sleep 60")

    info("*** Changing the link rate based on node mobility\n")
    # changing the link rate based on node mobility
    network_change(path, scenario, prediction_interval, sta1, 'sta1-wlan0',
                   '-latency 2000 -dest 10.0.0.3 -src 10.0.0.1',
                   buffer_size=buffer_size, exp_round=0,
                   log_dir=statistics_dir, event="sta1_events.csv")
    sleep(2)
    info("*** Start sending generated packets: sta1 (10.0.0.1) -> sta3 (10.0.0.3)\n")
    user_data_flow(2, sta1, sta3, statistics_dir)

    info("\n*** Running CLI\n")
    CLI(net)
    net.stop()
    os.system('sudo pkill xterm')
    out, err = subprocess.Popen(['pgrep', 'olsrd'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    if out:
        subprocess.Popen(['killall', 'olsrd'])


def get_init_positions(scenario: str, prediction_interval: int) -> Tuple[str, str, str]:
    path = os.path.dirname(os.path.abspath(__file__))
    file_ap = f"{path}/data/{scenario}/{scenario}_ref-node_pp.csv"
    df_ap = pd.read_csv(file_ap, dtype={'x': float, 'y': float})
    x_ap, y_ap = df_ap.loc[0, 'x'], df_ap.loc[0, 'y']
    columns = {'time': float, 'x': float, 'y': float, 'state': int,
               'x_pred': float, 'y_pred': float, 'state_pred': float}
    file_sta1 = f"{path}/data/{scenario}/{scenario}_sta1_{prediction_interval}-sec_pred-results_pp.csv"
    df_sta1 = pd.read_csv(file_sta1, dtype=columns)
    x_sta1, y_sta1 = df_sta1.loc[0, "x"], df_sta1.loc[0, "y"]
    file_sta3 = f"{path}/data/{scenario}/{scenario}_sta3_{prediction_interval}-sec_pred-results_pp.csv"
    df_sta3 = pd.read_csv(file_sta3, dtype=columns)
    x_sta3, y_sta3 = df_sta3.loc[0, "x"], df_sta3.loc[0, "y"]
    return f"{x_ap},{y_ap},0.0", f"{x_sta1},{y_sta1},0.0", f"{x_sta3},{y_sta3},0.0"


def get_trace(scenario: str, node: str, prediction_interval: int) -> pd.DataFrame:
    path = os.path.dirname(os.path.abspath(__file__))
    file = f"{path}/data/{scenario}/{scenario}_{node}_{prediction_interval}-sec_pred-results_pp.csv"
    df_trace = TraceReaderMobilityPrediction.read_trace(file)
    return df_trace


def network_change(path: str, scenario: str, prediction_interval: int, station1, interface1, extra_arg, buffer_size,
                   exp_round, log_dir, event, no_manet: bool = False):
    trace_file = f"{path}/data/{scenario}/{scenario}_{station1.name}_{prediction_interval}-sec_pred-results_pp.csv"
    trace_manet_file = f"{path}/data/{scenario}/{scenario}_{station1.name}_{prediction_interval}-sec_pred-results_NtoN.csv"
    # adding TC and NetEm rule
    if not no_manet:  # using olsr
        makeTerm(station1, title='Changing the network - ' + interface1,
                 cmd="python change_link_mobility_prediction.py -i " + interface1 + " -qlen " + str(
                     buffer_size) + " " + extra_arg + " -t '" + trace_file + "' -t2 '" + trace_manet_file + "' -e " +
                     log_dir + event + " ; sleep 20")
    else:  # no olsr
        makeTerm(station1, title='Changing the network - ' + interface1,
                 cmd="python change_link_mobility_prediction.py -i " + interface1 + " -qlen " + str(
                     buffer_size) + " " + extra_arg + " -t '" + trace_file + "'" + " ; sleep 20")
        # print("python change_link.py -i " + interface1 + " -qlen " + str(
        #             buffer_size) + " " + extra_arg + " -t '" + trace + "'")
    sleep(2)
    if log_dir:
        # makeTerm(station1, title='Qdisc', cmd="python packet_queue.py -i "+interface1)
        makeTerm(station1, title='Qdisc',
                 cmd="python packet_queue.py -i " + interface1 + " -o " + log_dir + station1.name + "_buffer.csv" +
                     " -r " + str(exp_round) + " -qlen " + str(buffer_size) + " ; sleep 20")
        # print("python packet_queue.py -i "+interface1+" -o "+log_dir+station1.name + "_buffer.csv" +
        #                                                     " -r " + str(exp_round) + " -qlen " + str(buffer_size))


def packet_sniffer(station1, station2, interface1, interface2, exp_round):
    command = "sudo python packet_sniffer.py -i " + interface2 + " -o recv_packets.csv -r " + exp_round + " -f 'udp and port 8999'"
    makeTerm(station2, title='Monitoring IP packets at Receiver', cmd=command)

    command = "sudo python packet_sniffer.py -i " + interface1 + " -o send_packets.csv -r " + exp_round + " -f '-p udp -m udp --dport 8999' -T True"
    makeTerm(station1, title='Monitoring IP packets at Sender', cmd=command)


def user_data_flow(scenario, station1, station2, statistics_dir):
    # Receiver
    # reference: http://traffic.comics.unina.it/software/ITG/manual/index.html
    # makeTerm(station2, title='Server',
    #          cmd="ITGRecv -Si sta3-eth2 -Sp 9090 -a 10.0.0.3 -i sta3-wlan0 -l {}/receiver.log".format(statistics_dir))

    makeTerm(station2, title='Server', cmd="ITGRecv -a 10.0.0.3 -i sta3-wlan0 -l {}/receiver.log".format(statistics_dir))
    sleep(10)

    if scenario == 1:
        # experiment 10 min Pendulum
        makeTerm(station1, title='Client',
                 cmd="ITGSend -T UDP -a 10.0.0.3 -U 2 30 -z 2500 -c 1264000 -s 0.123456 -t 10000000 -l {}/sender.log -c 1000 ; sleep 10".format(
                     statistics_dir))
        # makeTerm(station1, title='Client',
        #          cmd="ITGSend -Sda 192.168.0.3 -Sdp 9090 -T UDP -a 10.0.0.3 -U 2 30 -z 2500 -s 0.123456 -c 1264000 -t "
        #              "10000000 -l {}/sender.log -c 1000".format(statistics_dir))  # uhf
        # makeTerm(station1, title='Client',
        #          cmd="ITGSend -Sda 192.168.0.3 -Sdp 9090 -T UDP -a 10.0.0.3 -U 2 30 -z 2500 -s 0.123456 -c 1264 -t "
        #              "10000000 -l {}/sender.log -c 1000".format(statistics_dir))  # uhf
    if scenario == 2:
        # long experiment 30 min GM
        makeTerm(station1, title='Client',
                 cmd="ITGSend -T UDP -a 10.0.0.3 -U 2 20 -z 6000 -c 1264 -s 0.123456 -t 10000000 -l {}/sender.log -c 1000 ; sleep 10".format(
                     statistics_dir))
        # makeTerm(station1, title='Client',
        #          cmd="ITGSend -Sda 192.168.0.3 -Sdp 9090 -T UDP -a 10.0.0.3 -U 2 20 -z 6000 -s 0.123456 -c 1264 -t 10000000 "
        #              "-l {}/sender.log -c 1000".format(statistics_dir))  # uhf


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tactical network experiment!")
    parser.add_argument("-m", "--mobilityScenario", type=str, required=False, default=1,
                        help="Name of the scenario (the trace file has to have this as filename)")
    parser.add_argument("-p", "--predictionInterval", type=int, required=True,
                        help="Time in seconds how far into the future the model predicts "
                             "the network state in the given scenario")
    parser.add_argument("-d", "--disconnectState", type=float, default=0,
                        help="Predicted network state below which station disconnects (default: 0)")
    parser.add_argument("-r", "--reconnectState", type=float, default=1,
                        help="Minimal network state required to reconnect (default: 1)")
    parser.add_argument("-w", "--handoverDelay", type=int, default=0,
                        help="Delay in seconds between recognizing predicted disconnection "
                             "and initiating handover (default: 0)")
    parser.add_argument("-b", "--bufferSize", type=int, required=False, default=100,
                        help="Set the node buffer size (default: 100 packets)")
    parser.add_argument("-a", "--auto", action='store_true', required=False, default=False,
                        help="Automatically stop the experiment after the buffer is empty")
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    setLogLevel('info')
    args = parse_args()
    main(args.mobilityScenario, args.predictionInterval, args.disconnectState, args.reconnectState, args.handoverDelay,
         args.bufferSize, args.auto)
