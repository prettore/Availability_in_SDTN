##################################################
## stript to change the link bw using tc and netem
##################################################
## Author: Paulo H. L. Rettore
## Status: open
## Date: 06/07/2020
##################################################
import os
import sys
from subprocess import call
from time import sleep

import argparse
import pandas as pd
from datetime import datetime

# reading trace files
def get_trace(node, file_):
    df_trace = pd.read_csv(file_)
    df_trace['node'] = df_trace['node'].astype(int)
    trace_node = df_trace.groupby('node')
    state_interval = []
    state = []
    for n in trace_node.groups:
        if node == n:
            trace = trace_node.get_group(n)
            # for row in trace:
            for line in range(1, len(trace)):
                t = float(trace.loc[line - 1, "time"])
                t_1 = float(trace.loc[line, "time"])
                if line == 1:
                    state.append(int(float(trace.loc[line-1, "state"])))
                    state_interval.append(t_1 - t)
                state.append(int(float(trace.loc[line, "state"])))
                state_interval.append(t_1 - t)

    return state, state_interval

# function to create the qdisc
def setting_initial_rules(interface_arg, rate_arg, latency_arg, dest_ip, src_ip):
    # delliting rules
    call('tc qdisc del dev ' + interface_arg + ' root', shell=True)
    # increasing the queue len - Root qdisc and default queue length:
    call('ip link set dev ' + interface_arg + ' txqueuelen 10000', shell=True)

    #call('tc qdisc add dev ' + interface_arg + ' root handle 1: prio', shell=True)
    call('tc qdisc add dev ' + interface_arg + ' root handle 1: htb default 1', shell=True)
    call('tc class add dev ' + interface_arg + ' parent 1: classid 1:1 htb rate 9600bit', shell=True) #ceil 9600bit
    call('tc filter add dev ' + interface_arg + ' parent 1: protocol ip prio 1 u32 '
                                               ' match ip dst ' + dest_ip +' match ip src ' + src_ip +
                                               ' match ip protocol 17 0xff flowid 1:2', shell=True)  # match ip dport 8999 0xffff
    call('tc class add dev ' + interface_arg + ' parent 1:1 classid 1:2 htb rate ' + str(rate_arg) + 'bit',
         shell=True) #ceil 9600bit
    call('tc qdisc add dev ' + interface_arg + ' parent 1:2 handle 2: netem delay '+ latency_arg + 'ms ', shell=True)

# fuction to raplace the qdisc rules
def update_rules(interface_arg,latency_arg,dest_ip, src_ip, states,time_interval):

    datarate_dic = dict([(5,"9600"),
         (4,"4800"),(3,"2400"),(2,"1200"),
         (1,"600"),(0,"Previous")])
    print('***Starting ever-changing network***')

    for i in range(1,len(states)):
        #first case
        if i-1==0:
            # if a disconnected state appears set the data-rate manually
            if (states[i-1] == 0):
                setting_initial_rules(interface_arg, str(datarate_dic[4]), latency_arg, dest_ip, src_ip)
            else:
                print('0, State %d, Rate %s, Datetime %s for %f second' %
                      (states[i-1], datarate_dic[states[0]], datetime.now().strftime("%H:%M:%S"),
                       round(time_interval[i-1], ndigits=2)))
                setting_initial_rules(interface_arg, str(datarate_dic[states[i-1]]), latency_arg, dest_ip, src_ip)
            sleep(time_interval[i-1])
        else:
            print('%d, State %d, Rate %s, Datetime %s for %f second' % (
                i, states[i], datarate_dic[states[i]], datetime.now().strftime("%H:%M:%S"), round(time_interval[i],ndigits=2)))
            # if a disconnected state appears keep doing nothing
            if (states[i] == 0):
                sleep(time_interval[i])
            else:
                call('tc class replace dev ' + interface_arg + ' parent 1:10 classid 1:2 htb rate ' +
                     str(datarate_dic[states[i]]) + 'bit ', shell=True)
                sleep(time_interval[i])

if __name__ == '__main__':

    path = os.path.dirname(os.path.abspath(__file__)) + '/data/'
    #deley_variation = str(int(delay_arg) / 4)
    #latency_arg = str(4 * delay_arg)

    parser = argparse.ArgumentParser(description="Changing the Qdisc rules!")
    parser.add_argument("-i", "--interface", help="The interface to be shaped", type=str,
                        required=True)
    parser.add_argument("-rate", "--rate", help="Maximum rate in bit", type=str, default=9600)#, required=True)
    #parser.add_argument("-burst", "--burst", help="Maximum allowed burst in kbit", type=str, default=2048)#, required=True)
    parser.add_argument("-latency", "--latency", help="Latency parameter in ms", type=str, default=2000)#, required=True)
    parser.add_argument("-dest", "--dest", help="Destination ip - filtering packets by destination ip and udp protocol", type=str, required=True)
    parser.add_argument("-src", "--src", help="Source ip - filtering packets by Source ip and udp protocol", type=str, required=True)
    #parser.add_argument("-update", "--update", help="Boolean to update the qdisc rule", type=str, default='False')
    parser.add_argument("-t", "--traceFile", help="Trace file to update the qdisc rule", type=str, required=False)
    args = parser.parse_args()


    if args.interface and args.rate and args.latency and args.dest and args.src:
        setting_initial_rules(args.interface,args.rate,args.latency,args.dest,args.src)

    if args.interface and args.latency and args.dest and args.src and args.traceFile:
            states,state_interval = get_trace(0, path + args.traceFile)
            update_rules(args.interface,args.latency,args.dest,args.src,states,state_interval)


