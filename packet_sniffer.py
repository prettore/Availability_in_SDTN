##################################################
## stript to sniff ip packets
##################################################
## Author: Paulo H. L. Rettore and Sharath
## Status: open
## Date: 07/09/2020
##################################################
import csv
import os
import pyshark
import argparse
from collections import OrderedDict
from datetime import datetime


def parse_string(string):
    """
    function to convert acquired data to string format
    @param string:  data
    @return:        data in string format if it exists else return None to fill 'null' value in the corresponding table record
    """
    if not string:
        return None
    else:
        return str(string)

#create folder
def creatingFolders(dataFolder):
    if (os.path.isdir(dataFolder) == False):
        os.makedirs(dataFolder)

def capture_live_packets_iptables(interface,file,round,filter):

    print("***Starting packet sniffer!")
    #important commands
    #os.system('iptables-restore /temp/iptables-default')
    #os.system('iptables-save > /temp/iptables-default')
    os.system('iptables -A OUTPUT '+filter+' -o '+interface+' -j NFLOG --nflog-group 1')

    cap = pyshark.LiveCapture(interface='nflog:1', only_summaries=False, use_json=True, include_raw=True)
    cap.set_debug()
    while True:
        for packet in cap.sniff_continuously():
            packet_data_columns = ['packet_id', 'packet_timestamp', 'source_ip', 'destination_ip', 'protocol', 'packet_length','round']#, 'payload_length', 'payload','round']
            packet_data_dict = OrderedDict.fromkeys(packet_data_columns)

            packet_data_dict['packet_id'] = int(packet.ip.id, 0)#packet.number
            #packet_data_dict['frame_id'] = packet.frame_info.number
            packet_data_dict['packet_timestamp'] = str(packet.sniff_timestamp)#packet_sniff_time
            packet_data_dict['source_ip'] = parse_string(packet.ip.src_host)
            packet_data_dict['destination_ip'] = parse_string(packet.ip.dst_host)
            packet_data_dict['protocol'] = parse_string(packet.transport_layer)#parse_string(packet.highest_layer)
            packet_data_dict['packet_length'] = packet.length
            # payload = None
            # if 'data_raw' in packet:
            #    payload = packet.data_raw.value
            # elif 'packetbb_raw' in packet:
            #    payload = packet.packetbb_raw.value
            # packet_data_dict['payload'] = payload
            # payload_as_byte = bytearray.fromhex(payload)
            # payload_length = len(payload_as_byte)
            # packet_data_dict['payload_length'] = payload_length
            packet_data_dict['round'] = round

            print("Packet number: " + str(packet.number) + " packet id: " + str(int(packet.ip.id, 0)))
            try:
                if os.path.isfile(file):
                    with open(file, 'a') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=packet_data_columns)
                        writer.writerow(packet_data_dict)
                else:
                    with open(file, 'w') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=packet_data_columns)
                        writer.writeheader()
                        writer.writerow(packet_data_dict)
            except IOError:
                print("I/O error")

def capture_live_packets(interface,file,round,filter):

    print("***Starting packet sniffer!")

    cap = pyshark.LiveCapture(interface=interface, bpf_filter=filter,
                                  only_summaries=False, use_json=True, include_raw=True)
    #cap = pyshark.LiveCapture(interface=interface, only_summaries=False,
    #                          use_json=True, include_raw=True)
    cap.set_debug()
    while True:
        for packet in cap.sniff_continuously():
            packet_data_columns = ['packet_id', 'packet_timestamp', 'source_ip', 'destination_ip', 'protocol', 'packet_length','round']#, 'payload_length', 'payload','round']
            packet_data_dict = OrderedDict.fromkeys(packet_data_columns)

            packet_data_dict['packet_id'] = int(packet.ip.id, 0)#packet.number
            #packet_data_dict['frame_id'] = packet.frame_info.number
            #packet_sniff_time = datetime.strptime((str(packet.sniff_timestamp).replace('000 CEST','')),'%b %d, %Y %H:%M:%S.%f')
            #packet_sniff_time = parse_datetime_prefix(datetime_string=packet.sniff_timestamp,
            #                                          date_time_format='%b %d, %Y %H:%M:%S.%f')[:-2]
            #packet_data_dict['packet_timestamp'] = packet_sniff_time
            packet_data_dict['packet_timestamp'] = str(packet.sniff_timestamp)
            packet_data_dict['source_ip'] = parse_string(packet.ip.src_host)
            packet_data_dict['destination_ip'] = parse_string(packet.ip.dst_host)
            packet_data_dict['protocol'] = parse_string(packet.transport_layer)#parse_string(packet.highest_layer)
            packet_data_dict['packet_length'] = packet.length
            # payload = None
            # if 'data_raw' in packet:
            #    payload = packet.data_raw.value
            # elif 'packetbb_raw' in packet:
            #    payload = packet.packetbb_raw.value
            # packet_data_dict['payload'] = payload
            # payload_as_byte = bytearray.fromhex(payload)
            # payload_length = len(payload_as_byte)
            # packet_data_dict['payload_length'] = payload_length
            packet_data_dict['round'] = round

            print("Packet number: " + str(packet.number) + " packet id: " + str(int(packet.ip.id, 0)))
            try:
                if os.path.isfile(file):
                    with open(file, 'a') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=packet_data_columns)
                        writer.writerow(packet_data_dict)
                else:
                    with open(file, 'w') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=packet_data_columns)
                        writer.writeheader()
                        writer.writerow(packet_data_dict)
            except IOError:
                print("I/O error")

if __name__ == '__main__':

    path = os.path.dirname(os.path.abspath(__file__))
    creatingFolders(path+'/data/statistics/')

    parser = argparse.ArgumentParser(description="Packet Capture App!")
    parser.add_argument("-i", "--interface", help="The interface from which the packets have to be captured", type=str, default='sta2-wlan0')
    parser.add_argument("-o", "--outputFile", help="The file name that you wish to write data into", type=str, required=True)
    parser.add_argument("-r", "--expRound", help="The experiment round. Used to compute standard error and confidence interval", type=str,
                        default='0')
    parser.add_argument("-f", "--filter", help="Filter used to dump the packets", type=str,default='')
    parser.add_argument("-T", "--ptable", help="Acquire from Iptables", type=bool, default=False)
    args = parser.parse_args()
    if args.interface and args.outputFile:
        if args.ptable:
            capture_live_packets_iptables(str(args.interface), path + '/data/statistics/' + str(args.outputFile),
                                          str(args.expRound),str(args.filter))
        else:
            capture_live_packets(str(args.interface), path + '/data/statistics/' + str(args.outputFile),
                                 str(args.expRound), str(args.filter))
    else:
        print("Exiting of Packet Capture App! There are no enough arguments")
