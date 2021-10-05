##################################################
## stript compute network metrics from sender
# and receiver ip packets
##################################################
## Author: Paulo H. L. Rettore
## Status: open
## Date: 08/09/2020
##################################################

import csv
import os
import argparse
from collections import OrderedDict
from datetime import datetime
import pandas as pd
import numpy as np
import datetime
import time
from dateutil import parser

#create folder
def creatingFolders(dataFolder):
    if (os.path.isdir(dataFolder) == False):
        os.makedirs(dataFolder)

# convert string to timestamp to seconds
def timestamp_to_second(df,column_time):
    df[column_time] = pd.to_datetime(df[column_time])
    time_list = []

    for t in df[column_time]:
        if ~np.isnan(t.second):
            #time_list.append(time.mktime(t.timetuple()))
            time_list.append(t.timestamp())
        else:
            time_list.append(None)
    df[column_time] = time_list
    return df

# computing the bit rate
def computing_bit_rate(df,column_time,column_pct_len,window):
    bit_rate_dict = {}
    bits_received_second = []
    df_clear = df.copy()
    df_clear.dropna(inplace=True)

    df_clear[column_time] = df_clear[column_time].astype(int)
    df_grouped = df_clear.groupby(pd.cut(df_clear[column_time], np.arange(np.min(df_clear[column_time])-window, np.max(df_clear[column_time])+window, window)))
    #df_grouped = df_clear.groupby(column_time)
    for exp, df_s in df_grouped:
        bit_rate = sum((df_s[column_pct_len].astype(float).dropna()))*8/window#/ 1000
        for index, row in df_s.iterrows():
            bit_rate_dict[df_s.loc[index,'packet_id']] =  bit_rate
            #bits_received_second.append(bit_rate_dict)

    # filling gaps from the receiver side with 0 bitrate
    for index, row in df.iterrows():
        missing = False
        for key in bit_rate_dict:
            if df.loc[index, 'packet_id'] == key:
                bits_received_second.append(bit_rate_dict[key])
                missing = False
                break
            else:
                missing = True
        if missing:
            bits_received_second.append(0)

    # # computing using date time
    # df_clear = df.copy()
    # df_clear.dropna(inplace=True)
    # for j in range(0,len(df_clear)):
    #     df_clear.loc[j,column_time] = datetime.datetime.fromtimestamp(df_clear.loc[j,column_time])
    # bit_rate = (df_clear.resample('S', on=column_time, offset=str(5)+'s')[column_pct_len].sum()*8)/5
    ## bit_rate2 = (df_clear.groupby([pd.Grouper(key=column_time, freq=str(5)+'s')])[column_pct_len].sum()*8)/5
    # # filling gaps from the receiver side with 0 bitrate
    # for index in range(0,len(bit_rate),5):
    #     bits_received_second.append(bit_rate[index])

    return bits_received_second

# computing packet loss
def computing_packet_loss(df,column_bitrate,column_pct_loss):

    df[column_pct_loss] = df.apply(
        lambda row: 1 if (row[column_bitrate]==0) else 0, axis=1)

    pckt_loss = []
    for line in range(1, len(df)):
        p = df.loc[line-1,column_pct_loss]
        p_1 = df.loc[line,column_pct_loss]
        if line == 1:
            pckt_loss.append(p)
        if p_1 != 0:
            pckt_loss.append(pckt_loss[line-1]+p_1)
        else:
            pckt_loss.append(0)
    return pckt_loss

# compute the inter-packet delay or IP Packet Delay Variation (ipdv) or jitter
def computing_jitter(df,df_column_latency,column_jitter,df_column_time,column_bitrate):

    df.sort_values(by=df_column_time, inplace=True)# This sorts the date python 2.7
    df2 = df.reset_index(drop=True)

    # filter time based on existent bitrate computed from the receiver side
    df3 = df2[df2[column_bitrate] != 0]
    time_serie = df3[df_column_latency].reset_index(drop=True)

    jitter = []

    jitter.append(0)
    for line in range(1, len(time_serie)):
        l = time_serie[line - 1]
        l_1 = time_serie[line]
        jitter.append(np.abs(l_1 - l))

    # adding ipd into a correspondent row
    i = 0
    for index, row in df3.iterrows():
        df2.loc[index, column_jitter] = jitter[i]
        i = i + 1


    return df2


# # compute the inter-packet delay
# def inter_packet_delay2(df,df_column_time,column_ipd,column_bitrate):
#
#     df.sort_values(by=df_column_time, inplace=True)# This sorts the date python 2.7
#     df2 = df.reset_index(drop=True)
#
#     #filter time based on existent bitrate computed from the receiver side
#     df3 = df2[df2[column_bitrate]!=0]
#     time_serie = df3[df_column_time].reset_index(drop=True)
#
#     ipd = []
#
#     ipd.append(0)
#     for line in range(1, len(time_serie)):
#         p = time_serie[line - 1]
#         p_1 = time_serie[line]
#         ipd.append(p_1 - p)
#
#     #adding ipd into a correspondent row
#     i=0
#     for index, row in df3.iterrows():
#         df2.loc[index, column_ipd] = ipd[i]
#         i = i + 1
#
#     return df2

# compute the inter-packet delay
def interpotate_missed_timestamp(df,df_time,column1,column2,delay):

    if np.isnan(df_time.loc[0,column2]):
        df_time.loc[0,column2] = df.loc[0,column1] + delay
    if np.isnan(df_time.loc[len(df_time)-1, column2]):
        df_time.loc[len(df_time)-1, column2] = np.nanmax(df_time[column2]) + delay#df.loc[len(df)-1, column1] + delay

    df_time[column2] = df_time[column2].interpolate(method='linear', limit_direction='both', axis=0)

    return df_time

def processing_packets(path, sender,receiver,output):

    print("***Processing packets!")
    #packet_data_columns = ['packet_id', 'frame_id', 'packet_timestamp', 'source_ip', 'destination_ip', 'protocol', 'packet_length', 'payload_length', 'payload','round']
    packet_data_columns = ['packet_id', 'packet_timestamp', 'packet_length', 'round']
    bitrate_window = 30

    #read the csv files
    df_sender = pd.read_csv(path + sender, sep=',')
    df_receiver = pd.read_csv(path + receiver, sep=',')

    # filter the csv files
    df_sender = df_sender[packet_data_columns]
    df_receiver = df_receiver[packet_data_columns]

    # for unknown reasons so far there are duplicate packets ids
    # here we remove them from both sides which occur
    df_sender_unique = df_sender.drop_duplicates(subset=['packet_id'], keep='first')
    df_receiver_unique = df_receiver.drop_duplicates(subset=['packet_id'], keep='first')

    # group the df by the number of experiments (rounds)
    df_sender_grouped = df_sender_unique.groupby('round')
    df_receiver_grouped = df_receiver_unique.groupby('round')



    for exp, df_s in df_sender_grouped:
        # Creating summary df
        #csv_columns_summary = ['total_time_s', 'packet_sent', 'packet_received', 'packet_dropped', 'packet_dropped_pct',
        #                       'min_latency_s','max_latency_s', 'avg_latency_s', 'sd_latency_s', 'avg_jitter_s','sd_jitter_s',
        #                       'min_ipd_s','max_ipd_s','avg_ipd_s','sd_ipd_s', 'bytes_received','avg_bitrate',
        #                       'sd_bitrate', 'avg_packetrate_pkts','round']
        csv_columns_summary = ['total_time_s', 'packet_sent', 'packet_received', 'packet_dropped', 'packet_dropped_pct',
                               'min_latency_s','max_latency_s', 'avg_latency_s', 'sd_latency_s', 'avg_jitter_s','sd_jitter_s',
                               'bytes_received','avg_bitrate','sd_bitrate', 'avg_packetrate_pkts','round']
        df_summary = pd.DataFrame(columns=csv_columns_summary)


        # Creating df function of time
        #csv_columns_time_serie = ['time', 'bitrate', 'latency', 'jitter', 'inter_packet_delay', 'packet_loss', 'round']
        csv_columns_time_serie = ['time', 'bitrate', 'latency', 'jitter', 'packet_loss', 'round']
        df_time_serie = pd.DataFrame(columns=csv_columns_time_serie)

        #joining df sender and df receiver
        df_merged = df_s.merge(df_receiver_grouped.get_group(exp), on='packet_id', how='left')

        # sorting packets by sender timestamp
        df_merged.sort_values(by='packet_timestamp_x', inplace=True)  # This sorts the date python 2.7
        df_merged_sorted = df_merged.reset_index(drop=True)

        # convert string to timestamp to seconds
        #df_merged_sorted = timestamp_to_second(df_merged_sorted, 'packet_timestamp_x')
        #df_merged_sorted = timestamp_to_second(df_merged_sorted, 'packet_timestamp_y')

        # experiment duration
        df_summary.loc[exp-1, 'total_time_s'] = np.nanmax(df_merged_sorted['packet_timestamp_y']) - np.nanmin(df_merged_sorted['packet_timestamp_y'])#df_merged_sorted.iloc[-1]['packet_timestamp_x'] - df_merged_sorted.iloc[0]['packet_timestamp_x']
        df_time_serie['time'] = np.array(df_merged_sorted['packet_timestamp_y'])

        #end to end latency
        df_time_serie['latency'] = np.array(df_merged_sorted['packet_timestamp_y'] - df_merged_sorted['packet_timestamp_x'])
        df_summary.loc[exp-1, 'min_latency_s'] = np.nanmin(df_time_serie['latency'])
        df_summary.loc[exp-1, 'max_latency_s'] = np.nanmax(df_time_serie['latency'])
        df_summary.loc[exp-1, 'avg_latency_s'] = np.nanmean(df_time_serie['latency'])
        df_summary.loc[exp-1, 'sd_latency_s'] = np.nanstd(df_time_serie['latency'])

        # Packets
        df_summary.loc[exp - 1, 'packet_sent'] = len(df_merged_sorted['packet_timestamp_x'].dropna())# total packet sent
        df_summary.loc[exp - 1, 'packet_received'] = len(df_merged_sorted['packet_timestamp_y'].dropna())# total packet received
        df_summary.loc[exp - 1, 'packet_dropped'] = len(df_merged_sorted['packet_timestamp_x'].dropna()) - \
                                                    len(df_merged_sorted['packet_timestamp_y'].dropna())# total packet dropped
        df_summary.loc[exp - 1, 'packet_dropped_pct'] = df_summary.loc[exp - 1, 'packet_dropped']*100/\
                                                         df_summary.loc[exp-1, 'packet_sent']# packet rate
        df_summary.loc[exp - 1, 'avg_packetrate_pkts'] = df_summary.loc[exp - 1, 'packet_received']/\
                                                         df_summary.loc[exp-1, 'total_time_s']# packet rate

        # computing bit rate
        df_time_serie['bitrate'] = pd.Series(computing_bit_rate(df_merged_sorted,'packet_timestamp_y','packet_length_y',bitrate_window))
        #df_summary.loc[exp - 1, 'avg_bitrate'] = ((df_summary.loc[exp - 1, 'bytes_received'] * 8) / df_summary.loc[exp-1, 'total_time_s']) / 1000
        df_summary.loc[exp - 1, 'avg_bitrate'] = np.nanmean(df_time_serie['bitrate'])
        df_summary.loc[exp - 1, 'sd_bitrate'] = np.nanstd(df_time_serie['bitrate'])

        # bytes received
        df_summary.loc[exp - 1, 'bytes_received'] = sum((df_merged_sorted['packet_length_y'].astype(float).dropna()))

        # adding time values during the disconnection using interpolation
        df_time_serie = interpotate_missed_timestamp(df_merged_sorted, df_time_serie, 'packet_timestamp_x', 'time',df_summary.loc[exp-1, 'avg_latency_s'])
        #df_time_serie['time'] = df_time_serie['time'].interpolate(method='linear', limit_direction='both', axis=0)

        # # this computation needs to be after all other metrics
        # # inter-packet delay
        # #df_time_serie = inter_packet_delay(df_merged_sorted, df_time_serie, 'packet_timestamp_y', 'time', 'inter_packet_delay')
        # df_time_serie = inter_packet_delay2(df_time_serie, 'time', 'inter_packet_delay','bitrate')
        # df_summary.loc[exp - 1, 'min_ipd_s'] = np.nanmin(df_time_serie['inter_packet_delay'])
        # df_summary.loc[exp - 1, 'max_ipd_s'] = np.nanmax(df_time_serie['inter_packet_delay'])
        # df_summary.loc[exp - 1, 'avg_ipd_s'] = np.nanmean(df_time_serie['inter_packet_delay'])
        # df_summary.loc[exp - 1, 'sd_ipd_s'] = np.nanstd(df_time_serie['inter_packet_delay'])

        # this computation needs to be after all other metrics
        # computing jitter or the inter-packet delay or IP Packet Delay Variation (ipdv)
        # Jitter is the amount of variation in latency/response time, in milliseconds.
        # Reliable connections consistently report back the same latency over and over again.
        # Lots of variation (or 'jitter') is an indication of problems.
        # The 'Jitter' is calculated by taking the difference between latency samples.
        #df_time_serie['jitter'] = np.array(np.abs(df_time_serie['latency'] - df_summary.loc[exp -1, 'avg_latency_s']))
        df_time_serie = computing_jitter(df_time_serie, 'latency', 'jitter','time','bitrate')
        df_summary.loc[exp - 1, 'avg_jitter_s'] = np.mean(df_time_serie['jitter'])
        df_summary.loc[exp - 1, 'sd_jitter_s'] = np.nanstd(df_time_serie['jitter'])

        # adding packet loss values during the disconnection
        df_time_serie['packet_loss'] = computing_packet_loss(df_time_serie, 'bitrate', 'packet_loss')


        # # adding inter packet delay values during the disconnection
        # df_time_serie['inter_packet_delay'] = df_time_serie.apply(
        #     lambda row: 0 if np.isnan(row['time']) else row['inter_packet_delay'], axis=1)

        # # adding jitter values during the disconnection
        # df_time_serie['jitter'] = df_time_serie.apply(
        #     lambda row: 0 if np.isnan(row['time']) else row['jitter'], axis=1)
        # # adding latency values during the disconnection
        # df_time_serie['latency'] = df_time_serie.apply(
        #     lambda row: 0 if np.isnan(row['time']) else row['latency'], axis=1)

        # converting timestamp in datetime format
        time_format = []
        for ts in df_time_serie['time']:
            if ~np.isnan(ts):
                time_format.append(datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S.%f'))
            else:
                time_format.append(np.nan)
        df_time_serie['time'] = time_format


        # adding the experiment round
        df_summary.loc[exp - 1, 'round'] = exp
        df_time_serie['round'] = exp

        # saving statistics
        if os.path.isfile(path + output):
            df_summary.to_csv(path + output, mode='a', index=False,header=False)
            df_time_serie.to_csv(path + output.replace(".csv", "_metrics.csv"), mode='a', index=False,header=False)
        else:
            df_summary.to_csv(path + output, index=False)
            df_time_serie.to_csv(path + output.replace(".csv", "_metrics.csv"), index=False)

    # # removing raw data
    # print("***Processing done. Raw data removed!")
    # os.system("sudo rm " + path + sender)
    # os.system("sudo rm " + path + receiver)

if __name__ == '__main__':

    path = os.path.dirname(os.path.abspath(__file__))
    creatingFolders(path+'/data/statistics/')

    parser = argparse.ArgumentParser(description="Processing packets metrics!")
    parser.add_argument("-s", "--senderFile", help="File name of sender ip packets", type=str, required=True)
    parser.add_argument("-r", "--receiverFile", help="File name of receiver ip packets", type=str, required=True)
    parser.add_argument("-o", "--outputFile", help="The file name that you wish to write data into", type=str, required=True)

    args = parser.parse_args()
    if args.senderFile and args.receiverFile and args.outputFile:
        processing_packets(path+'/data/statistics/',str(args.senderFile),str(args.receiverFile),str(args.outputFile))
    else:
        print("Exiting of Packet Capture App! There are no enough arguments")




# import csv
# import os
# import argparse
# from collections import OrderedDict
# from datetime import datetime
# import pandas as pd
# import numpy as np
# import datetime
# import time
# from dateutil import parser
#
# #create folder
# def creatingFolders(dataFolder):
#     if (os.path.isdir(dataFolder) == False):
#         os.makedirs(dataFolder)
#
# # convert string to timestamp to seconds
# def timestamp_to_second(df,column_time):
#     df[column_time] = pd.to_datetime(df[column_time])
#     time_list = []
#
#     for t in df[column_time]:
#         if ~np.isnan(t.second):
#             #time_list.append(time.mktime(t.timetuple()))
#             time_list.append(t.timestamp())
#         else:
#             time_list.append(None)
#     df[column_time] = time_list
#     return df
#
# # computing the bit rate
# def computing_bit_rate(df,column_time,column_pct_len):
#     bit_rate_dict = {}
#     bits_received_second = []
#     df_clear = df.copy()
#     df_clear.dropna(inplace=True)
#     df_clear[column_time] = df_clear[column_time].astype(int)
#     df_grouped = df_clear.groupby(column_time)
#     for exp, df_s in df_grouped:
#         bit_rate = sum((df_s[column_pct_len].astype(float).dropna()))*8/ 1000
#         for index, row in df_s.iterrows():
#             bit_rate_dict[df_s.loc[index,'packet_id']] =  bit_rate
#             #bits_received_second.append(bit_rate_dict)
#
#     # filling gaps from the receiver side with 0 bitrate
#     for index, row in df.iterrows():
#         missing = False
#         for key in bit_rate_dict:
#             if df.loc[index, 'packet_id'] == key:
#                 bits_received_second.append(bit_rate_dict[key])
#                 missing = False
#                 break
#             else:
#                 missing = True
#         if missing:
#             bits_received_second.append(0)
#     return bits_received_second
#
# # computing packet loss
# def computing_packet_loss(df,column_time,column_pct_loss):
#
#     df[column_pct_loss] = df.apply(
#         lambda row: 1 if np.isnan(row[column_time]) else 0, axis=1)
#
#     pckt_loss = []
#     for line in range(1, len(df)):
#         p = df.loc[line-1,column_pct_loss]
#         p_1 = df.loc[line,column_pct_loss]
#         if line == 1:
#             pckt_loss.append(p)
#         if p_1 != 0:
#             pckt_loss.append(pckt_loss[line-1]+p_1)
#         else:
#             pckt_loss.append(0)
#     return pckt_loss
#
# # # compute the inter-packet delay
# # def inter_packet_delay(df,df_out,df_column_time,df_out_column_time,column_ipd):
# #
# #     df.sort_values(by=df_column_time,inplace=True)#,inplace=True, ignore_index=True)  # This sorts the date python 2.7
# #     df2 = df.reset_index(drop=True)
# #     ipd = []
# #     for line in range(1, len(df2)):
# #
# #         if np.isnan(df2.loc[line,df_column_time]):
# #             ipd.append(np.NaN)
# #         else:
# #             p = df2.loc[line-1,df_column_time]#trace.iloc[line-1,1]
# #             p_1 = df2.loc[line,df_column_time]#trace.iloc[line,1]
# #
# #             if line == 1:
# #                 ipd.append(0)
# #             if np.isnan(p_1-p):
# #                ipd.append(0)
# #             else:
# #                 ipd.append(p_1 - p)
# #
# #     df_out.sort_values(by=df_out_column_time, inplace=True)
# #     df_out[column_ipd] = np.array(ipd)
# #
# #     return df_out
#
# # compute the inter-packet delay
# def inter_packet_delay2(df,df_column_time,column_ipd,column_bitrate):
#
#     df.sort_values(by=df_column_time, inplace=True)# This sorts the date python 2.7
#     df2 = df.reset_index(drop=True)
#     ipd = []
#     for line in range(1, len(df2)):
#         p = df2.loc[line - 1, df_column_time]
#         p_1 = df2.loc[line, df_column_time]
#         if line == 1:
#             if (np.isnan(df2.loc[line-1,column_bitrate])) | (df2.loc[line-1,column_bitrate] == 0):
#                 ipd.append(np.NaN)
#             else:
#                 ipd.append(0)
#
#         if (np.isnan(df2.loc[line,column_bitrate])) | (df2.loc[line,column_bitrate] == 0):
#             ipd.append(np.NaN)
#         else:
#             if (np.isnan(df2.loc[line-1, column_bitrate])) | (df2.loc[line-1, column_bitrate] == 0):
#                 ipd.append(0)
#             else:
#                 ipd.append(p_1 - p)
#
#     df2[column_ipd] = np.array(ipd)
#
#     return df2
#
# # compute the inter-packet delay
# def interpotate_missed_timestamp(df,df_time,column1,column2,delay):
#
#     if np.isnan(df_time.loc[0,column2]):
#         df_time.loc[0,column2] = df.loc[0,column1] + delay
#     if np.isnan(df_time.loc[len(df_time)-1, column2]):
#         df_time.loc[len(df_time)-1, column2] = df.loc[len(df)-1, column1] + delay
#
#     df_time[column2] = df_time[column2].interpolate(method='linear', limit_direction='both', axis=0)
#
#     return df_time
#
# def processing_packets(path, sender,receiver,output):
#
#     print("***Processing packets!")
#     #packet_data_columns = ['packet_id', 'frame_id', 'packet_timestamp', 'source_ip', 'destination_ip', 'protocol', 'packet_length', 'payload_length', 'payload','round']
#     packet_data_columns = ['packet_id', 'packet_timestamp', 'packet_length', 'round']
#
#     #read the csv files
#     df_sender = pd.read_csv(path + sender, sep=',')
#     df_receiver = pd.read_csv(path + receiver, sep=',')
#
#     # filter the csv files
#     df_sender = df_sender[packet_data_columns]
#     df_receiver = df_receiver[packet_data_columns]
#
#     # for unknown reasons so far there are duplicate packets ids
#     # here we remove them from both sides which occur
#     df_sender_unique = df_sender.drop_duplicates(subset=['packet_id'], keep='first')
#     df_receiver_unique = df_receiver.drop_duplicates(subset=['packet_id'], keep='first')
#
#     # group the df by the number of experiments (rounds)
#     df_sender_grouped = df_sender_unique.groupby('round')
#     df_receiver_grouped = df_receiver_unique.groupby('round')
#
#
#
#     for exp, df_s in df_sender_grouped:
#         # Creating summary df
#         csv_columns_summary = ['total_time_s', 'packet_sent', 'packet_received', 'packet_dropped', 'packet_dropped_pct',
#                                'min_latency_s','max_latency_s', 'avg_latency_s', 'sd_latency_s', 'avg_jitter_s','sd_jitter_s',
#                                'min_ipd_s','max_ipd_s','avg_ipd_s','sd_ipd_s', 'bytes_received','avg_bitrate',
#                                'sd_bitrate', 'avg_packetrate_pkts','round']
#         df_summary = pd.DataFrame(columns=csv_columns_summary)
#
#
#         # Creating df function of time
#         csv_columns_time_serie = ['time', 'bitrate', 'latency', 'jitter', 'inter_packet_delay', 'packet_loss', 'round']
#         #csv_columns_time_serie = ['time', 'bitrate', 'latency', 'jitter', 'packet_loss', 'round']
#         df_time_serie = pd.DataFrame(columns=csv_columns_time_serie)
#
#         #joining df sender and df receiver
#         df_merged = df_s.merge(df_receiver_grouped.get_group(exp), on='packet_id', how='left')
#
#         # convert string to timestamp to seconds
#         df_merged = timestamp_to_second(df_merged, 'packet_timestamp_x')
#         df_merged = timestamp_to_second(df_merged, 'packet_timestamp_y')
#
#         # experiment duration
#         df_summary.loc[exp-1, 'total_time_s'] = np.nanmax(df_merged['packet_timestamp_x']) - np.nanmin(df_merged['packet_timestamp_x'])#df_merged.iloc[-1]['packet_timestamp_x'] - df_merged.iloc[0]['packet_timestamp_x']
#         df_time_serie['time'] = np.array(df_merged['packet_timestamp_y'])
#
#         #end to end latency
#         #latency_and_ipd = np.array(inter_packet_delay(df_merged, 'packet_timestamp_y')) + np.array(df_merged['packet_timestamp_y'] - df_merged['packet_timestamp_x'])
#         #df_time_serie['latency'] = np.array(inter_packet_delay(df_merged, 'packet_timestamp_y'))# inter_packet_delay
#         df_time_serie['latency'] = np.array(df_merged['packet_timestamp_y'] - df_merged['packet_timestamp_x'])
#         #df_time_serie['latency'] = latency_and_ipd
#         df_summary.loc[exp-1, 'min_latency_s'] = np.nanmin(df_time_serie['latency'])
#         df_summary.loc[exp-1, 'max_latency_s'] = np.nanmax(df_time_serie['latency'])
#         df_summary.loc[exp-1, 'avg_latency_s'] = np.nanmean(df_time_serie['latency'])
#         df_summary.loc[exp-1, 'sd_latency_s'] = np.nanstd(df_time_serie['latency'])
#
#         # Packets
#         df_summary.loc[exp - 1, 'packet_sent'] = len(df_merged['packet_timestamp_x'].dropna())# total packet sent
#         df_summary.loc[exp - 1, 'packet_received'] = len(df_merged['packet_timestamp_y'].dropna())# total packet received
#         df_summary.loc[exp - 1, 'packet_dropped'] = len(df_merged['packet_timestamp_x'].dropna()) - \
#                                                     len(df_merged['packet_timestamp_y'].dropna())# total packet dropped
#         df_summary.loc[exp - 1, 'packet_dropped_pct'] = df_summary.loc[exp - 1, 'packet_dropped']*100/\
#                                                          df_summary.loc[exp-1, 'packet_sent']# packet rate
#         df_summary.loc[exp - 1, 'avg_packetrate_pkts'] = df_summary.loc[exp - 1, 'packet_received']/\
#                                                          df_summary.loc[exp-1, 'total_time_s']# packet rate
#
#         # computing bit rate
#         df_time_serie['bitrate'] = pd.Series(computing_bit_rate(df_merged,'packet_timestamp_y','packet_length_y'))
#         #df_summary.loc[exp - 1, 'avg_bitrate'] = ((df_summary.loc[exp - 1, 'bytes_received'] * 8) / df_summary.loc[exp-1, 'total_time_s']) / 1000
#         df_summary.loc[exp - 1, 'avg_bitrate'] = np.nanmean(df_time_serie['bitrate'])
#         df_summary.loc[exp - 1, 'sd_bitrate'] = np.nanstd(df_time_serie['bitrate'])
#
#         # bytes received
#         df_summary.loc[exp - 1, 'bytes_received'] = sum((df_merged['packet_length_y'].astype(float).dropna()))
#
#         # computing jitter
#         df_time_serie['jitter'] = np.array(np.abs(df_time_serie['latency'] - df_summary.loc[exp -1, 'avg_latency_s']))
#         df_summary.loc[exp - 1, 'avg_jitter_s'] = np.mean(df_time_serie['jitter'])
#         df_summary.loc[exp - 1, 'sd_jitter_s'] = np.nanstd(df_time_serie['jitter'])
#
#         # adding packet loss values during the disconnection
#         df_time_serie['packet_loss'] = computing_packet_loss(df_time_serie, 'time', 'packet_loss')
#
#         # adding time values during the disconnection using interpolation
#         df_time_serie = interpotate_missed_timestamp(df_merged, df_time_serie, 'packet_timestamp_x', 'time',df_summary.loc[exp-1, 'avg_latency_s'])
#         #df_time_serie['time'] = df_time_serie['time'].interpolate(method='linear', limit_direction='both', axis=0)
#
#
#         # this computation needs to be after all other metrics
#         # inter-packet delay
#         #df_time_serie = inter_packet_delay(df_merged, df_time_serie, 'packet_timestamp_y', 'time', 'inter_packet_delay')
#         df_time_serie = inter_packet_delay2(df_time_serie, 'time', 'inter_packet_delay','bitrate')
#         df_summary.loc[exp - 1, 'min_ipd_s'] = np.nanmin(df_time_serie['inter_packet_delay'])
#         df_summary.loc[exp - 1, 'max_ipd_s'] = np.nanmax(df_time_serie['inter_packet_delay'])
#         df_summary.loc[exp - 1, 'avg_ipd_s'] = np.nanmean(df_time_serie['inter_packet_delay'])
#         df_summary.loc[exp - 1, 'sd_ipd_s'] = np.nanstd(df_time_serie['inter_packet_delay'])
#
#         # # adding inter packet delay values during the disconnection
#         # df_time_serie['inter_packet_delay'] = df_time_serie.apply(
#         #     lambda row: 0 if np.isnan(row['time']) else row['inter_packet_delay'], axis=1)
#
#
#         # # adding jitter values during the disconnection
#         # df_time_serie['jitter'] = df_time_serie.apply(
#         #     lambda row: 0 if np.isnan(row['time']) else row['jitter'], axis=1)
#         # # adding latency values during the disconnection
#         # df_time_serie['latency'] = df_time_serie.apply(
#         #     lambda row: 0 if np.isnan(row['time']) else row['latency'], axis=1)
#
#         # converting timestamp in datetime format
#         time_format = []
#         for ts in df_time_serie['time']:
#             if ~np.isnan(ts):
#                 time_format.append(datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S.%f'))
#             else:
#                 time_format.append(np.nan)
#         df_time_serie['time'] = time_format
#
#
#         # adding the experiment round
#         df_summary.loc[exp - 1, 'round'] = exp
#         df_time_serie['round'] = exp
#
#         # saving statistics
#         if os.path.isfile(path + output):
#             df_summary.to_csv(path + output, mode='a', index=False,header=False)
#             df_time_serie.to_csv(path + output.replace(".csv", "_metrics.csv"), mode='a', index=False,header=False)
#         else:
#             df_summary.to_csv(path + output, index=False)
#             df_time_serie.to_csv(path + output.replace(".csv", "_metrics.csv"), index=False)
#
# if __name__ == '__main__':
#
#     path = os.path.dirname(os.path.abspath(__file__))
#     creatingFolders(path+'/data/statistics/')
#
#     parser = argparse.ArgumentParser(description="Processing packets metrics!")
#     parser.add_argument("-s", "--senderFile", help="File name of sender ip packets", type=str, required=True)
#     parser.add_argument("-r", "--receiverFile", help="File name of receiver ip packets", type=str, required=True)
#     parser.add_argument("-o", "--outputFile", help="The file name that you wish to write data into", type=str, required=True)
#
#     args = parser.parse_args()
#     if args.senderFile and args.receiverFile and args.outputFile:
#         processing_packets(path+'/data/statistics/',str(args.senderFile),str(args.receiverFile),str(args.outputFile))
#     else:
#         print("Exiting of Packet Capture App! There are no enough arguments")
