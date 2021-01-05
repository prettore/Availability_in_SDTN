##################################################
## stript to evaluate mobility on TN over ever
## change data rates
##################################################
## Author: Paulo H. L. Rettore
## Status: open
## Date: 01/07/2020
##################################################
import os
import signal
import sys
from time import sleep

import subprocess

import argparse
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.node import Controller, OVSKernelSwitch
#from mininet.term import makeTerm
from mininet.term import cleanUpScreens, makeTerm
from mn_wifi.link import wmediumd, adhoc
from mn_wifi.net import Mininet_wifi
from mn_wifi.node import OVSKernelAP
from mn_wifi.replaying import ReplayingMobility
from mn_wifi.wmediumdConnector import interference
import numpy as np
import pandas as pd


#reading trace files
def get_trace_bitrate(file_):
    datarate_dic = dict([(5, "9600"),
                         (4, "4800"),
                         (3, "2400"),
                         (2, "1200"),
                         (1, "600")])

    df_trace = pd.read_csv(file_)
    df_trace['node'] = df_trace['node'].astype(int)
    trace_node = df_trace.groupby('node')

    for n in trace_node.groups:

        trace = trace_node.get_group(n)
        #for row in trace:
        for index, row in trace.iterrows():
            x = row['x']
            y = row['y']
            t = row['time']

#reading trace files
def get_trace(sta_list, file_,smooth):

    df_trace = pd.read_csv(file_)
    df_trace['node'] = df_trace['node'].astype(int)
    trace_node = df_trace.groupby('node')

    for n in trace_node.groups:
        sta_list[n].time = []
        sta_list[n].p = []
        #sta_list[n].position = (-1000, 0, 0)
        if smooth:
            sta_list[n].coord = []
        trace = trace_node.get_group(n)
        #for row in trace:
        for index, row in trace.iterrows():
            x = row['x']
            y = row['y']
            t = row['time']
            if smooth:
                sta_list[n].coord.append(str(x) + "," + str(y) + ",0.0")
            pos = float(x), float(y), 0.0
            sta_list[n].p.append(pos)
            sta_list[n].time.append(t)

def stopXterms( self ):
    "Kill each xterm."
    for term in self.terms:
        os.kill( term.pid, signal.SIGKILL)
    cleanUpScreens()

#creating mininet_ex wifi topology with mobility
def topology(traceFile,expRound):

    info("Create a network\n")
    net = Mininet_wifi(controller=Controller,link=wmediumd, wmediumd_mode=interference,
                       noise_th=-91, fading_cof=3)

    info("*** Creating nodes\n")
    sta1 = net.addStation('sta1', position='130.0,120.0,0.0',speed=1, range=100)
    sta2 = net.addStation('sta2', position='120.0,120.0,0.0',speed=1, range=100)
    sta3 = net.addStation('sta3', position='220.0,80.0,0.0',speed=1, range=200, color='gray')

    c1 = net.addController('c1')
    s1 = net.addSwitch('s1', cls=OVSKernelSwitch, failMode='standalone')

    info("*** Configuring Propagation Model\n")
    net.setPropagationModel(model="logDistance", exp=5.5)
    # net.setPropagationModel(model="logNormalShadowing", sL=2.1, exp=6, variance=4)

    info("*** Configuring wifi nodes\n")
    net.configureWifiNodes()

    info("*** Creating wired links\n")
    net.addLink(sta1, s1)
    net.addLink(sta2, s1)
    sta1.setIP('192.168.0.1/24', intf='sta1-eth1')
    sta2.setIP('192.168.0.2/24', intf='sta2-eth1')
    sta1.setMAC('00:00:00:00:00:03', intf='sta1-eth1')
    sta2.setMAC('00:00:00:00:00:04', intf='sta2-eth1')


    info("*** Creating overlay links\n")
    # MANET routing protocols supported by proto:
    # babel, batman_adv, batmand and olsr
    # WARNING: we may need to stop Network Manager if you want
    # to work with babel
    protocols = 'olsr'  # ['babel', 'batman_adv', 'batmand', 'olsr']
    net.addLink(sta1, cls=adhoc, intf='sta1-wlan0', mode='g',
                ssid='adhocNet', ht_cap='HT40+',channel=5, proto=protocols)
    net.addLink(sta2, cls=adhoc, intf='sta2-wlan0', mode='g',
                ssid='adhocNet', ht_cap='HT40+',channel=5, proto=protocols)
    #net.addLink(sta3, cls=adhoc, intf='sta3-wlan0', mode='g',
    #            ssid='adhocNet', ht_cap='HT40+',channel=5, proto=protocols)

    info("*** Modifying link rate\n")
    # adding TC and Netem rule
    makeTerm(sta1, cmd="python change_link.py -i sta1-wlan0 -rate 4800 -latency 2000 -dest 10.0.0.2/8 -src 10.0.0.1/8")
    makeTerm(sta3, cmd="python change_link.py -i sta3-wlan0 -rate 240000 -latency 2000")


    info("*** Configuring motion mode\n")
    path = os.path.dirname(os.path.abspath(__file__)) + '/data/'

    # reading traces
    get_trace([sta1, sta2, sta3], path+traceFile, smooth_motion)


    # smooth motion - ReplayingMobility
    if smooth_motion:
        # getting position from external trace and setting mobitity function
        net.startMobility(time=0, mob_rep=1, reverse=True)
        net.mobility(sta1, 'start', time=int(sta1.time[0]), position=sta1.coord[0])
        net.mobility(sta1, 'stop', time=int(sta1.time[len(sta1.time)-1]), position=sta1.coord[len(sta1.coord)-1])

        net.startMobility(time=0, mob_rep=1, reverse=True)
        net.mobility(sta2, 'start', time=int(sta2.time[0]), position=sta2.coord[0])
        net.mobility(sta2, 'stop', time=int(sta2.time[len(sta2.time) - 1]), position=sta2.coord[len(sta2.coord) - 1])

        net.startMobility(time=0, mob_rep=1, reverse=True)
        net.mobility(sta3, 'start', time=int(sta3.time[0]), position=sta3.coord[0])
        net.mobility(sta3, 'stop', time=int(sta3.time[len(sta3.time) - 1]), position=sta3.coord[len(sta3.coord) - 1])


        net.stopMobility(time=int(sta1.time[len(sta1.time) - 1]))
    # trace motion - ReplayingMobility
    else:
        # setting mobility based on external trace (position and time)
        net.isReplaying = True


    info("*** Creating plot\n")
    net.plotGraph(max_x=250, max_y=250)

    info("*** Starting network\n")
    net.build()
    c1.start()
    s1.start([c1])
    #net.startTerms()
    #sleep(2)

    info("*** Changing the link rate based on node mobility\n")
    if smooth_motion == False:
        info("\n*** Replaying Mobility\n")
        ReplayingMobility(net)
    sleep(10) # time to sync mobility simulation and changing link
    # adding TC and Netem rule
    makeTerm(sta1, title='Changing the network',
             cmd="python change_link.py -i sta1-wlan0 -latency 2000 -dest 10.0.0.2/8 -src 10.0.0.1/8 -t " + args.traceFile)
    sleep(2)
    makeTerm(sta1, title='Qdisc', cmd="python packet_queue.py -i sta1-wlan0")


    info("*** Starting packet sniffer\n")
    command = "sudo python packet_sniffer.py -i sta2-wlan0 -o recv_"+ traceFile.replace('Trace_','packets_') +\
              " -r "+ expRound +" -f 'udp and port 8999'"
    makeTerm(sta2, title = 'Monitoring IP packets at Receiver', cmd=command)
    command = "sudo python packet_sniffer.py -i sta1-wlan0 -o send_"+ traceFile.replace('Trace_','packets_') +\
              " -r " + expRound +" -f '-p udp -m udp --dport 8999' -T True"
    makeTerm(sta1, title = 'Monitoring IP packets at Sender', cmd=command)
    sleep(2)

    info("*** Testing data flow\n")
    # reference: http://traffic.comics.unina.it/software/ITG/manual/index.html
    makeTerm(sta2, title = 'Server', cmd="ITGRecv -Si sta2-eth1 -Sp 9090 -a 10.0.0.2")
    #makeTerm(sta2, title = 'Server', cmd="ITGRecv -a 10.0.0.2")
    #makeTerm(sta2, title = 'Server', cmd="iperf -B 10.0.0.2 -u -s -i 3 -p 8999")
    #info("\n*** Starting data flow after 20s\n")
    sleep(5)
    #makeTerm(sta1, title = 'Client', cmd="ITGSend -T UDP -a 10.0.0.2 -c 1264 -s 0.123456 -U .5 10 -z 100 -t 10000000")
    makeTerm(sta1, title = 'Client', cmd="ITGSend -Sda 192.168.0.2 -Sdp 9090 -T UDP -a 10.0.0.2 -c 1264 -s 0.123456 -z 100 -t 6000000")# -l sender.log -x receiver.log")
    #makeTerm(sta1, title = 'Client', cmd="iperf -u -c 10.0.0.2 -n 0.01 -i 1 -t 10 -p 8999")#> iperf_result.txt")
    #makeTerm(sta1, title = 'Ping', cmd="ping 10.0.0.2")

    info("*** Running CLI\n")
    CLI(net)
    print("Log the experiment...\n")
    logs_IP = 'sudo python packet_processing.py -s send_packets_'+traceFile.replace('Trace_','')+' -r recv_packets_'+traceFile.replace('Trace_','')+' -o ip_statistics_'+traceFile.replace('Trace_','')
    os.system(logs_IP)
    info("*** Stopping network\n")
    os.system('sudo pkill xterm')
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    parser = argparse.ArgumentParser(description="Tactical network experiment!")
    parser.add_argument("-smooth", "--smooth", help="Add speed between nodes", type=bool, required=False, default=False)
    parser.add_argument("-auto", "--auto", help="Auto experiment", type=bool, required=False, default=False)
    parser.add_argument("-t", "--traceFile", help="Input trace file", type=str, required=True)
    parser.add_argument("-r", "--expRound", help="The experiment round. Used to compute standard "
                                                 "error and confidence interval", type=str, default='0')
    args = parser.parse_args()

    smooth_motion = args.smooth#True if '-smooth' in sys.argv else False
    auto = args.auto#True if '-auto' in sys.argv else False

    if args.traceFile:
        topology(str(args.traceFile),str(args.expRound))
    else:
        print("Exiting the experiment! There are no enough arguments")

