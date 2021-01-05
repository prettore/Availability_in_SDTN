##################################################
## stript to log pecket from the qdisc
##################################################
## Author: Paulo H. L. Rettore
## Status: open
## Date: 02/11/2020
##################################################
import os
import subprocess
from subprocess import call
import sys
import json
import re
#import commands
from time import sleep


def main():
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
        #result = str(commands.getoutput(command_str))

        # result = subprocess.getoutput(command_str)
        result_queue = str(subprocess.check_output(command_str,shell = True))

        command_str = 'tc -s class show dev ' + interface_arg
        result_rate = str(subprocess.check_output(command_str, shell=True))

        #"class htb 1:2 root leaf 2: prio rate 4800bit ceil 4800bit burst 1599b cburst 1599b"
        #rate_str = re.search(re.escape('rate ') + "(.*)" + re.escape(' ceil'), result_rate).group(1)
        #queued_str = re.search(re.escape('overlimits ') + "(.*)" + re.escape('requeues'), result_rate).group(1)
        rate_str = re.findall(re.escape('rate ') + "(.*)" + re.escape(' ceil'), result_rate)[1]
        queued_str = re.findall(re.escape('overlimits ') + "(.*)" + re.escape('requeues'), result_rate)[1]

        #fixing errors from json
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
        result_queue = "[{" +result_queue+"}]"
        #print("TEST:"+str(result))
        result_js = json.loads(result_queue)

        packet_requeues = "0"
        total_packet = "0"
        packet_over = 0
        packet_drops = "0"
        queue_len = "0"
        for rule in result_js:
            if "htb" == rule['kind']:
                total_packet = str(rule['packets'])
                packet_over = queued_str #str(rule['overlimits'])
                packet_requeues = str(rule['requeues'])
                packet_drops = str(rule['drops'])
                queue_len = int(rule['qlen'])

        if queue_len == 0:
            print("Rate: "+ str(rate_str)+' Queue packet total/queued/requeued/drop/len: '+total_packet+'/'+packet_over.strip()+'/'+packet_requeues+'/'+packet_drops+'/'+str(queue_len))
            with open('packet_queue.txt', 'w') as file:
                file.write('False')
            return False
        else:
            print("Rate: "+ str(rate_str)+' Queue packet total/queued/requeued/drop/len: '+total_packet+'/'+packet_over.strip()+'/'+packet_requeues+'/'+packet_drops+'/'+str(queue_len))
            with open('packet_queue.txt', 'w') as file:
                file.write('True')
            return True

        # print("TEST:"+result)

    except ImportError:
        pass



if __name__ == '__main__':

    interface_arg = ""
    if len(sys.argv) > 1:
        #rule_arg = sys.argv[1]
        if sys.argv[1] == "-i":
            interface_arg = sys.argv[2]

        has_packet = True
        while has_packet:
            main()
            sleep(1)
    else:
        print("""
            Parameters:
            Arg[1] -> '-i' <interface parameter>
            Arg[2] -> '<network interface>'
            """)
