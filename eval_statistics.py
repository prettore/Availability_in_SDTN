import os
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, FormatStrFormatter


def main(path: str):
    send_packets = path + 'send_packets.csv'
    recv_packets = path + 'recv_packets.csv'
    packet_data_sender = np.genfromtxt(send_packets, delimiter=",", names=["packet_id", "packet_timestamp"],
                                       skip_header=1)
    packet_data_receiver = np.genfromtxt(recv_packets, delimiter=",", names=["packet_id", "packet_timestamp"],
                                         skip_header=1)
    send_signal = path + 'sta1-wlan0_signal.csv'
    recv_signal = path + 'sta3-wlan0_signal.csv'
    names = ["time", "ssid", "signal", "signal_avg", "rx_bitrate", "tx_bitrate", "expected_throughput"]
    signal_data_sender = np.genfromtxt(send_signal, delimiter=",", dtype=None, autostrip=True, names=names,
                                       skip_header=1)
    signal_data_receiver = np.genfromtxt(recv_signal, delimiter=",", dtype=None, autostrip=True, names=names,
                                         skip_header=1)

    fig, ax = plt.subplots(3, 1, figsize=(15, 12))

    times = [t for t in packet_data_sender["packet_timestamp"]] + [t for t in packet_data_receiver["packet_timestamp"]]
    times += [float(t) for t in signal_data_sender["time"]] + [float(t) for t in signal_data_receiver["time"]]
    starttime = min(times)
    endtime = max(times)

    t_axis_packets = list()
    packet_loss = list()
    delay = list()
    for i, j in enumerate(packet_data_sender["packet_id"]):
        t_axis_packets.append(packet_data_sender["packet_timestamp"][i] - starttime)
        if j in packet_data_receiver["packet_id"]:
            k = [id for id in packet_data_receiver["packet_id"]].index(j)
            packet_loss.append(0)
            delay.append(packet_data_receiver["packet_timestamp"][k] - packet_data_sender["packet_timestamp"][i])
        else:
            delay.append(0)
            packet_loss.append(1)



    t_axis_sender = [float(t) - starttime for t in signal_data_sender["time"]]
    signal_sender = [float(s.rstrip(b' dBm')) for s in signal_data_sender["signal"]]
    signal_sender_smoothed = []
    for i, j in enumerate(signal_sender):
        if i == 0:
            average = j
        elif i == 1:
            average = (j + signal_sender[i - 1]) / 2
        else:
            average = (j + signal_sender[i - 1] + signal_sender[i - 2]) / 3
        signal_sender_smoothed.append(average)
    line1 = ax[0].plot(t_axis_sender, signal_sender, label='Signal strength sender', marker='v', color='tab:blue', linewidth=0)
    line11 = ax[0].plot(t_axis_sender, signal_sender_smoothed, label='Signal strength sender moving avg.', marker=',', color='tab:blue')
    ax[0].set_xlabel("Time (seconds)")
    ax[0].set_ylabel("Signal AP (dBm)")
    ax[0].legend()

    t_axis_receiver = [float(t) - starttime for t in signal_data_receiver["time"]]
    signal_receiver = [float(s.rstrip(b' dBm')) for s in signal_data_receiver["signal"]]
    signal_receiver_smoothed = []
    for i, j in enumerate(signal_receiver):
        if i == 0:
            average = j
        elif i == 1:
            average = (j + signal_receiver[i - 1]) / 2
        else:
            average = (j + signal_receiver[i - 1] + signal_receiver[i - 2]) / 3
        signal_receiver_smoothed.append(average)
    line2 = ax[0].plot(t_axis_receiver, signal_receiver, label='Signal strength receiver', marker='x', color='tab:orange', linewidth=0)
    line22 = ax[0].plot(t_axis_receiver, signal_receiver_smoothed, label='Signal strength receiver moving avg.', marker=',', color='tab:orange')
    ax[0].set_xlabel("Time (seconds)")
    ax[0].set_ylabel("Signal AP (dBm)")
    ax[0].legend()
    ax[0].grid()

    line0 = ax[1].plot(t_axis_packets, packet_loss, label='Packet loss', marker='2', linewidth=0)
    ax[1].set_xlabel("Time (seconds)")
    ax[1].set_ylabel("Packet lost (1=yes, 0=no)")
    ax[1].set_yticks([0.0, 1.0])
    ax[1].set_ylim(-1, 3)
    ax[1].legend()
    ax[1].yaxis.grid()

    line3 = ax[2].plot(t_axis_packets, delay, label='Delay', marker='')
    ax[2].set_xlabel("Time (seconds)")
    ax[2].set_ylabel("Delay (seconds)")
    ax[2].legend()
    ax[2].grid()

    for x in ax:
        x.set_xlim(-5, endtime - starttime + 5)
        x.xaxis.set_major_locator(MultipleLocator(20))
        x.xaxis.set_major_formatter(FormatStrFormatter('%d'))
        x.xaxis.set_minor_locator(MultipleLocator(2.5))

    plt.tight_layout()
    plt.show()

    # starttime = min(data_sender["packet_timestamp"] + data_receiver["packet_timestamp"])
    # t_sender = list()
    # for i in data_sender["packet_timestamp"]:
    #     t_sender.append(i - starttime)


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
