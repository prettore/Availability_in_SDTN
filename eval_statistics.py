import os
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
from collections import deque


def main(path: str):
    send_packets = path + 'send_packets.csv'
    recv_packets = path + 'recv_packets.csv'
    packet_data_columns = ['packet_id', 'packet_timestamp', 'packet_length']

    # read the csv files
    df_sender = pd.read_csv(send_packets, sep=',')
    df_receiver = pd.read_csv(recv_packets, sep=',')

    # filter the csv files
    df_sender = df_sender[packet_data_columns]
    df_receiver = df_receiver[packet_data_columns]

    # for unknown reasons so far there are duplicate packets ids
    # here we remove them from both sides which occur
    df_sender_unique = df_sender.drop_duplicates(subset=['packet_id'], keep='first')
    df_receiver_unique = df_receiver.drop_duplicates(subset=['packet_id'], keep='first')

    # create summary dataframe
    csv_columns_summary = ['total_time_s', 'packet_sent', 'packet_received', 'packet_dropped', 'packet_dropped_rate',
                           'min_latency_s', 'max_latency_s', 'avg_latency_s', 'sd_latency_s', 'avg_jitter_s',
                           'sd_jitter_s', 'avg_packetrate_pkts', 'round']
    # summary_dict = {k: None for k in csv_columns_summary}
    df_summary = pd.DataFrame(columns=csv_columns_summary)

    # create time series dataframe
    csv_columns_time_series = ['time', 'latency', 'jitter', 'packet_loss']
    df_time_series = pd.DataFrame(columns=csv_columns_time_series)

    # join df sender and df receiver
    df_merged = df_sender_unique.merge(df_receiver_unique, on='packet_id', how='left', suffixes=('_send', '_recv'))

    # sorting packets by sender timestamp
    df_merged.sort_values(by='packet_timestamp_send', inplace=True)  # This sorts the date python 2.7
    df_merged_sorted = df_merged.reset_index(drop=True)

    df_merged_sorted.to_csv(path + 'merged_packets.csv', index=False)

    # experiment duration
    df_summary.loc[0, 'total_time_s'] = np.nanmax(df_merged_sorted['packet_timestamp_recv']) - np.nanmin(
        df_merged_sorted['packet_timestamp_recv'])
    df_time_series['time'] = np.array(df_merged_sorted['packet_timestamp_recv']) - np.nanmin(
        df_merged_sorted['packet_timestamp_recv'])

    # end to end latency and latency summary
    df_time_series['latency'] = np.array(
        df_merged_sorted['packet_timestamp_recv'] - df_merged_sorted['packet_timestamp_send'])
    df_summary.loc[0, 'min_latency_s'] = np.nanmin(df_time_series['latency'])
    df_summary.loc[0, 'max_latency_s'] = np.nanmax(df_time_series['latency'])
    df_summary.loc[0, 'avg_latency_s'] = np.nanmean(df_time_series['latency'])
    df_summary.loc[0, 'sd_latency_s'] = np.nanstd(df_time_series['latency'])

    # Packets summary
    df_summary.loc[0, 'packet_sent'] = len(df_merged_sorted['packet_timestamp_send'].dropna())  # total packet sent
    df_summary.loc[0, 'packet_received'] = len(df_merged_sorted['packet_timestamp_recv'].dropna())  # total packet received
    df_summary.loc[0, 'packet_dropped'] = len(df_merged_sorted['packet_timestamp_send'].dropna()) - len(
        df_merged_sorted['packet_timestamp_recv'].dropna())  # total packet dropped
    df_summary.loc[0, 'packet_dropped_rate'] = df_summary.loc[0, 'packet_dropped'] * 100 / df_summary.loc[0, 'packet_sent'] # packet drop rate
    df_summary.loc[0, 'avg_packetrate_pkts'] = df_summary.loc[0, 'packet_received'] / df_summary.loc[0, 'total_time_s']  # packet rate

    # calculate packet loss
    df_time_series['packet_loss'] = df_time_series.apply(
        lambda row: 1 if np.isnan(row['time']) else 0, axis='columns')
    for row in range(1, len(df_time_series)):
        p0 = df_time_series.loc[row-1, 'packet_loss']
        p1 = df_time_series.loc[row, 'packet_loss']
        if p1 != 0:
            df_time_series.loc[row, 'packet_loss'] = p0 + p1
        else:
            df_time_series.loc[row, 'packet_loss'] = 0

    # calculate jitter
    df_tmp = df_time_series.dropna(subset=['time']).reset_index(drop=False)
    for row, _ in df_tmp.iterrows():
        if row == 0:
            df_tmp.loc[row, 'jitter'] = 0
        else:
            l0 = df_tmp.loc[row-1, 'latency']
            l1 = df_tmp.loc[row, 'latency']
            df_tmp.loc[row, 'jitter'] = np.abs(l1 - l0)
    for row, _ in df_tmp.iterrows():
        index = df_tmp.loc[row, 'index']
        jitter = df_tmp.loc[row, 'jitter']
        df_time_series.loc[index, 'jitter'] = jitter

    # interpolate missed timestamp
    if np.isnan(df_time_series.loc[0, 'time']):
        df_time_series.loc[0, 'time'] = df_merged_sorted.loc[0, 'packet_timestamp_send'] + df_summary.loc[0, 'avg_latency_s']
    if np.isnan(df_time_series.loc[len(df_time_series)-1, 'time']):
        df_time_series.loc[len(df_time_series)-1, 'time'] = np.nanmax(df_time_series['time']) + df_summary.loc[0, 'avg_latency_s']
    df_time_series['time'] = df_time_series['time'].interpolate(method='linear', limit_direction='both', axis=0)

    # df_summary = pd.DataFrame.from_dict(summary_dict)
    df_summary.to_csv(path + 'summary.csv', index=False)
    df_time_series.to_csv(path + 'metrics_time_series.csv', index=False)

    packet_data_sender = np.genfromtxt(send_packets, delimiter=",", names=["packet_id", "packet_timestamp"],
                                       skip_header=1)
    packet_data_receiver = np.genfromtxt(recv_packets, delimiter=",", names=["packet_id", "packet_timestamp"],
                                         skip_header=1)
    send_signal = path + 'sta1-wlan0_signal.csv'
    recv_signal = path + 'sta3-wlan0_signal.csv'
    names = ["time", "ssid", "signal", "signal_avg", "rx_bitrate", "tx_bitrate"]
    signal_data_sender = np.genfromtxt(send_signal, delimiter=",", dtype=None, autostrip=True, names=names,
                                       skip_header=1, encoding='UTF-8')
    signal_data_receiver = np.genfromtxt(recv_signal, delimiter=",", dtype=None, autostrip=True, names=names,
                                         skip_header=1, encoding='UTF-8')

    times = [t for t in packet_data_sender["packet_timestamp"]] + [t for t in packet_data_receiver["packet_timestamp"]]
    times += [float(t) for t in signal_data_sender["time"]] + [float(t) for t in signal_data_receiver["time"]]
    starttime = min(times)
    endtime = max(times)

    t_axis_packets = list()
    packet_loss = list()
    delay = list()
    for i, j in enumerate(packet_data_sender["packet_id"]):
        if packet_data_sender["packet_timestamp"][i] - starttime <= 160:
            t_axis_packets.append(packet_data_sender["packet_timestamp"][i] - starttime)
            if j in packet_data_receiver["packet_id"]:
                k = [packet_id for packet_id in packet_data_receiver["packet_id"]].index(j)
                packet_loss.append(0)
                delay.append(packet_data_receiver["packet_timestamp"][k] - packet_data_sender["packet_timestamp"][i])
            else:
                delay.append(0)
                packet_loss.append(1)
        else:
            break

    t_axis_signal_sender = [float(t) - starttime for t in signal_data_sender["time"] if float(t) - starttime <= 160]
    signal_sender = [float(s.rstrip(' dBm')) for s in signal_data_sender["signal"][:len(t_axis_signal_sender)]]
    signal_avg_sender = [s for s in signal_data_sender["signal_avg"][:len(t_axis_signal_sender)]]

    t_axis_signal_receiver = [float(t) - starttime for t in signal_data_receiver["time"] if float(t) - starttime <= 160]
    signal_receiver = [float(s.rstrip(' dBm')) for s in signal_data_receiver["signal"][:len(t_axis_signal_receiver)]]
    signal_avg_receiver = [s for s in signal_data_receiver["signal_avg"][:len(t_axis_signal_receiver)]]

    fig, ax = plt.subplots(3, 1, figsize=(10, 10))

    line1 = ax[0].plot(t_axis_signal_sender, signal_sender, label='Signal strength sender', marker='v', color='tab:blue', linewidth=0)
    line11 = ax[0].plot(t_axis_signal_sender, signal_avg_sender, label='Signal strength sender moving avg.', marker=',', color='tab:blue')
    ax[0].set_xlabel("Time (seconds)")
    ax[0].set_ylabel("Signal AP (dBm)")
    ax[0].legend()

    line2 = ax[0].plot(t_axis_signal_receiver, signal_receiver, label='Signal strength receiver', marker='x', color='tab:orange', linewidth=0)
    line22 = ax[0].plot(t_axis_signal_receiver, signal_avg_receiver, label='Signal strength receiver moving avg.', marker=',', color='tab:orange')
    ax[0].set_xlabel("Time (seconds)")
    ax[0].set_ylabel("Signal AP (dBm)")
    ax[0].legend()
    ax[0].grid()

    # line0 = ax[1].plot(t_axis_packets, packet_loss, label='Packet loss', marker='2', linewidth=0)
    line0 = ax[1].plot(df_time_series['time'], df_time_series['packet_loss'], label='Packet loss', marker='2', linewidth=0)
    ax[1].set_xlabel("Time (seconds)")
    ax[1].set_ylabel("Packet lost (1=yes, 0=no)")
    # ax[1].set_yticks([0.0, 1.0])
    # ax[1].set_ylim(-1, 3)
    ax[1].legend()
    ax[1].yaxis.grid()

    # line3 = ax[2].plot(t_axis_packets, delay, label='Delay', marker='')
    line3 = ax[2].plot(df_time_series['time'], df_time_series['latency'], label='Latency', marker='')
    ax[2].set_xlabel("Time (seconds)")
    ax[2].set_ylabel("End-to-end Latency (seconds)")
    ax[2].legend()
    ax[2].grid()

    for x in ax:
        x.set_xlim(-5, endtime - starttime + 5)
        x.xaxis.set_major_locator(MultipleLocator(20))
        x.xaxis.set_major_formatter(FormatStrFormatter('%d'))
        x.xaxis.set_minor_locator(MultipleLocator(2.5))

    plt.tight_layout()
    plt.show()


def timestamp_to_second(df, column_time):
    """Convert string to timestamp to seconds"""
    df[column_time] = pd.to_datetime(df[column_time])
    time_list = []
    for t in df[column_time]:
        if ~np.isnan(t.second):
            time_list.append(t.timestamp())
        else:
            time_list.append(None)
    df[column_time] = time_list
    return df


def rolling_mean(x, window: int):
    window_deque = deque(maxlen=window)
    rolling_means = []
    for i in x:
        window_deque.append(i)
        rolling_means.append(sum(window_deque) / len(window_deque))
    return rolling_means


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Tactical network experiment!")
    parser.add_argument("-d", "--directory", help="Directory of log files", type=str, required=True)
    # parser.add_argument("-s", "--senderpackets", help="Packet list sender", type=str)
    # parser.add_argument("-r", "--receiverpackets", help="Packet list receiver", type=str)
    # parser.add_argument("-S", "--sendersignal", help="Signal strength log file sender", type=str)
    # parser.add_argument("-R", "--receiversignal", help="Signal strength log file receiver", type=str)
    args = parser.parse_args()
    path = args.directory
    main(path)
