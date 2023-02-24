##################################################
## stript to log packet from the qdisc
##################################################
## Author: Paulo H. L. Rettore
## Status: open
## Date: 02/4/2021
##################################################
import os
import subprocess
from datetime import datetime
from subprocess import call
import sys
import json
import re
# import commands
from time import sleep
from collections import OrderedDict
import csv
import argparse


def creatingFolders(dataFolder):
    if (os.path.isdir(dataFolder) == False):
        os.makedirs(dataFolder)


def qdiscLog(interface_arg):
    try:
        # result_rate = '''class htb 1:1 root rate 9600bit ceil 9600bit burst 1599b cburst 1599b
        #                  Sent 54852 bytes 42 pkt (dropped 0, overlimits 2 requeues 0)
        #                  backlog 0b 0p requeues 0
        #                  lended: 0 borrowed: 0 giants: 0
        #                  tokens: 3828119 ctokens: 3828119
        #                 class htb 1:2 parent 1:1 leaf 2: prio rate 4800bit ceil 4800bit burst 1599b cburst 1599b
        #                  Sent 54852 bytes 42 pkt (dropped 0, overlimits 41 requeues 0)
        #                  backlog 75748b 58p requeues 0
        #                  lended: 42 borrowed: 0 giants: 0
        #                  tokens: -34002357 ctokens: -34002357'''

        command_str = 'tc -s -j qdisc show dev ' + interface_arg
        # result = call(command_str, shell=True)
        # result = str(commands.getoutput(command_str))

        # result = subprocess.getoutput(command_str)
        result_queue = str(subprocess.check_output(command_str, shell=True))
        # result_queue= ""

        command_str = 'tc -s class show dev ' + interface_arg
        result_rate = str(subprocess.check_output(command_str, shell=True))

        # version 1
        # rate_str = re.findall(re.escape('rate ') + "(.*)" + re.escape(' ceil'), result_rate)[1]
        # queued_str = re.findall(re.escape('overlimits ') + "(.*)" + re.escape('requeues'), result_rate)[1]

        # version 2
        rate_str = re.findall(r'rate (.*?) ceil', result_rate)[1]
        queued_str = re.findall(r'overlimits (.*?) requeues', result_rate)[1]

        # version 3
        #rate_str = [x.group() for x in
        # re.finditer(r'rate (.*?) ceil', result_rate)]


        # fixing errors from json
        result_queue = result_queue.split("[{")[1]
        result_queue = result_queue.replace('\\n', '')
        result_queue = result_queue.split("},{")[0]

        # print("TEST:"+result)
        # result = result.replace('\\n', '')
        # print("TEST:"+result)
        # result = result.split("}]")[0]
        # print("TEST:"+result)
        if "maxpacket" in result_queue:
            result_queue = result_queue.split("maxpacket")[0]
        result_queue = "[{" + result_queue + "}]"
        # print("TEST:"+str(result))
        result_js = json.loads(result_queue)

        packet_requeues = "0"
        total_packet = "0"
        packet_over = 0
        packet_drops = "0"
        queue_len = "0"
        for rule in result_js:
            if "htb" == rule['kind']:
                total_packet = str(rule['packets'])
                packet_over = queued_str  # str(rule['overlimits'])
                packet_requeues = str(rule['requeues'])
                packet_drops = str(rule['drops'])
                queue_len = int(rule['qlen'])

        if queue_len == 0:
            print("Rate: " + str(
                rate_str) + ' Queue packet total/queued/requeued/drop/len: ' + total_packet + '/' + packet_over.strip() + '/' + packet_requeues + '/' + packet_drops + '/' + str(
                queue_len))
            with open('packet_queue.txt', 'w') as file:
                file.write('False')
            return False
        else:
            print("Rate: " + str(
                rate_str) + ' Queue packet total/queued/requeued/drop/len: ' + total_packet + '/' + packet_over.strip() + '/' + packet_requeues + '/' + packet_drops + '/' + str(
                queue_len))
            with open('packet_queue.txt', 'w') as file:
                file.write('True')
            return True

        # print("TEST:"+result)

    except ImportError:
        pass


def bufferLog(interface_arg, buffer_size, file, ex_round, start_time: float):
    buffer_columns = ['buffer_timestamp', 'data_throughput', 'pr4g_queue_occupancy', 'round']

    try:
        buffer_data_dict = OrderedDict.fromkeys(buffer_columns)

        command_str = 'tc -s -j qdisc show dev ' + interface_arg
        result_queue = str(subprocess.check_output(command_str, shell=True))

        command_str = 'tc -s class show dev ' + interface_arg
        result_rate = str(subprocess.check_output(command_str, shell=True))

        rate_str = re.findall(r'rate (.*?) ceil', result_rate)[1]
        #queued_str = re.findall(r'overlimits (.*?) requeues', result_rate)[1]


        # fixing errors from json
        result_queue = result_queue.split("[{")[1]
        result_queue = result_queue.replace('\\n', '')
        result_queue = result_queue.split("},{")[0]

        if "maxpacket" in result_queue:
            result_queue = result_queue.split("maxpacket")[0]
        result_queue = "[{" + result_queue + "}]"
        # print("TEST:"+str(result))
        result_js = json.loads(result_queue)

        queue_len = "0"
        for rule in result_js:
            if "htb" == rule['kind']:
                queue_len = int(rule['qlen'])

                buffer_data_dict['buffer_timestamp'] = datetime.now().timestamp() - start_time
                buffer_data_dict['data_throughput'] = rate_str.replace('bit', '')
                buffer_data_dict['pr4g_queue_occupancy'] = round(
                    float(rule['qlen']) / float(buffer_size) * 100, 2)
                buffer_data_dict['round'] = ex_round

        print(buffer_data_dict)

        try:
            if os.path.isfile(file):
                with open(file, 'a') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=buffer_columns)
                    writer.writerow(buffer_data_dict)
            else:
                with open(file, 'w') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=buffer_columns)
                    writer.writeheader()
                    writer.writerow(buffer_data_dict)

            pq_dir = file.replace('_buffer', '_packet_queue').replace('.csv','.txt')
            if queue_len == 0:
                with open(pq_dir, 'w') as file:
                    file.write('False')
                return False
            else:
                with open(pq_dir, 'w') as file:
                    file.write('True')
                return True

        except IOError:
            print("I/O error")

    except ImportError:
        pass


if __name__ == '__main__':

    #path = str(os.getcwd()) + "/"
    #creatingFolders(path + 'data/statistics/')

    parser = argparse.ArgumentParser(description="Creating buffer using NFQUEUE!")
    parser.add_argument("-i", "--interface", help="The interface to get the qdisc stats", type=str,
                        required=False)
    parser.add_argument("-qlen", "--queuelen", help="Maximum queue size in packets", type=int, required=False,
                        default=100)
    parser.add_argument("-o", "--outputFile", help="The file name that you wish to write data into", type=str,
                        required=False)
    parser.add_argument("-r", "--expRound", help="The experiment round. Used to compute standard error and confidence "
                                                 "interval", type=str, default='0')
    parser.add_argument("-t", "--start-time",
                        help="Timestamp of the start of the experiment as synchronizing reference for measurements",
                        type=float, required=True)
    args = parser.parse_args()
    has_packet = True

    if args.interface and args.outputFile:
        while has_packet:
            #bufferLog(args.interface, args.queuelen, path + 'data/statistics/' + str(args.outputFile), args.expRound)
            bufferLog(args.interface, args.queuelen, str(args.outputFile), args.expRound, args.start_time)
            sleep(1)
    elif args.interface:
        while has_packet:
            qdiscLog(args.interface)
            sleep(1)

# ##################################################
# ## stript to log pecket from the qdisc
# ##################################################
# ## Author: Paulo H. L. Rettore
# ## Status: open
# ## Date: 02/11/2020
# ##################################################


# import os
# import subprocess
# from subprocess import call
# import sys
# import json
# import re
# #import commands
# from time import sleep
#
#
# def main():
#     try:
#         # result_rate = '''class htb 1:1 root rate 9600bit ceil 9600bit burst 1599b cburst 1599b
#         #                  Sent 54852 bytes 42 pkt (dropped 0, overlimits 2 requeues 0)
#         #                  backlog 0b 0p requeues 0
#         #                  lended: 0 borrowed: 0 giants: 0
#         #                  tokens: 3828119 ctokens: 3828119
#         #                 class htb 1:2 parent 1:1 leaf 2: prio rate 4800bit ceil 4800bit burst 1599b cburst 1599b
#         #                  Sent 54852 bytes 42 pkt (dropped 0, overlimits 41 requeues 0)
#         #                  backlog 75748b 58p requeues 0
#         #                  lended: 42 borrowed: 0 giants: 0
#         #                  tokens: -34002357 ctokens: -34002357'''
#
#         command_str = 'tc -s -j qdisc show dev ' + interface_arg
#         # result = call(command_str, shell=True)
#         #result = str(commands.getoutput(command_str))
#
#         # result = subprocess.getoutput(command_str)
#         result_queue = str(subprocess.check_output(command_str,shell = True))
#
#         command_str = 'tc -s class show dev ' + interface_arg
#         result_rate = str(subprocess.check_output(command_str, shell=True))
#
#         #"class htb 1:2 root leaf 2: prio rate 4800bit ceil 4800bit burst 1599b cburst 1599b"
#         #rate_str = re.search(re.escape('rate ') + "(.*)" + re.escape(' ceil'), result_rate).group(1)
#         #queued_str = re.search(re.escape('overlimits ') + "(.*)" + re.escape('requeues'), result_rate).group(1)
#         rate_str = re.findall(re.escape('rate ') + "(.*)" + re.escape(' ceil'), result_rate)[1]
#         queued_str = re.findall(re.escape('overlimits ') + "(.*)" + re.escape('requeues'), result_rate)[1]
#
#         #fixing errors from json
#         result_queue = result_queue.split("[{")[1]
#         result_queue = result_queue.replace('\\n', '')
#         result_queue = result_queue.split("},{")[0]
#
#         # print("TEST:"+result)
#         # result = result.replace('\\n', '')
#         # print("TEST:"+result)
#         # result = result.split("}]")[0]
#         # print("TEST:"+result)
#         if "maxpacket" in result_queue:
#               result_queue = result_queue.split("maxpacket")[0]
#         result_queue = "[{" +result_queue+"}]"
#         #print("TEST:"+str(result))
#         result_js = json.loads(result_queue)
#
#         packet_requeues = "0"
#         total_packet = "0"
#         packet_over = 0
#         packet_drops = "0"
#         queue_len = "0"
#         for rule in result_js:
#             if "htb" == rule['kind']:
#                 total_packet = str(rule['packets'])
#                 packet_over = queued_str #str(rule['overlimits'])
#                 packet_requeues = str(rule['requeues'])
#                 packet_drops = str(rule['drops'])
#                 queue_len = int(rule['qlen'])
#
#         if queue_len == 0:
#             print("Rate: "+ str(rate_str)+' Queue packet total/queued/requeued/drop/len: '+total_packet+'/'+packet_over.strip()+'/'+packet_requeues+'/'+packet_drops+'/'+str(queue_len))
#             with open('packet_queue.txt', 'w') as file:
#                 file.write('False')
#             return False
#         else:
#             print("Rate: "+ str(rate_str)+' Queue packet total/queued/requeued/drop/len: '+total_packet+'/'+packet_over.strip()+'/'+packet_requeues+'/'+packet_drops+'/'+str(queue_len))
#             with open('packet_queue.txt', 'w') as file:
#                 file.write('True')
#             return True
#
#         # print("TEST:"+result)
#
#     except ImportError:
#         pass
#
#
#
# if __name__ == '__main__':
#
#     interface_arg = ""
#     if len(sys.argv) > 1:
#         #rule_arg = sys.argv[1]
#         if sys.argv[1] == "-i":
#             interface_arg = sys.argv[2]
#
#         has_packet = True
#         while has_packet:
#             main()
#             sleep(1)
#     else:
#         print("""
#             Parameters:
#             Arg[1] -> '-i' <interface parameter>
#             Arg[2] -> '<network interface>'
#             """)
