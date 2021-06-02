import argparse
from datetime import datetime

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import gridspec

from matplotlib.ticker import MultipleLocator, FormatStrFormatter


def main2(data_path, show, noolsr):
    summary_file = data_path + 'summary.csv'
    time_series_file = data_path + 'metrics_time_series.csv'

    # read the csv files
    df_summary = pd.read_csv(summary_file, sep=',')
    df_time_series = pd.read_csv(time_series_file, sep=',')

    summary_columns = ['total_time_s', 'packet_sent', 'packet_received', 'packet_dropped', 'packet_dropped_rate',
                       'min_latency_s', 'max_latency_s', 'avg_latency_s', 'sd_latency_s', 'avg_jitter_s',
                       'sd_jitter_s', 'avg_packetrate_pkts', 'round']
    df_summary = df_summary[summary_columns]

    time_series_columns = ['time', 'latency', 'jitter', 'packet_loss']
    df_time_series = df_time_series[time_series_columns]

    # df_time_series['time'] = df_time_series['time'].apply(lambda x: x / 60)
    df_time_series['time'] = np.array(df_time_series['time']) / 60
    print(df_time_series['time'])

    df_packet_loss_peaks = df_time_series[
        (df_time_series.packet_loss > 0) & (df_time_series.packet_loss.shift(-1) == 0)].append(
        df_time_series.tail(1)[df_time_series.tail(1).packet_loss > 0])
    print("Packet loss peaks:\n", df_packet_loss_peaks)

    send_signal_file = data_path + 'sta1-wlan0_signal.csv'
    send_events_file = data_path + 'sta1_events.csv'
    recv_signal_file = data_path + 'sta3-wlan0_signal.csv'
    recv_events_file = data_path + 'sta3_events.csv'
    signal_columns = ["time", "SSID", "signal", "signal_avg", "rx_bitrate", "tx_bitrate"]
    events_columns = ['time', 'disconnect', 'reconnect', 'scanner_start', 'scanner_stop', 'scan_trigger']

    df_signal_send = pd.read_csv(send_signal_file, sep=',')
    df_events_send = pd.read_csv(send_events_file, sep=',')
    df_signal_recv = pd.read_csv(recv_signal_file, sep=',')
    df_events_recv = pd.read_csv(recv_events_file, sep=',')

    df_signal_send = df_signal_send[signal_columns]
    df_events_send = df_events_send[events_columns]
    df_signal_recv = df_signal_recv[signal_columns]
    df_events_recv = df_events_recv[events_columns]

    send_disconnect_start = []
    send_disconnect_stop = []
    send_reconnect_start = []
    send_reconnect_stop = []
    for i, row in df_events_send.iterrows():
        if df_events_send.loc[i, 'disconnect'] == 1:
            send_disconnect_start.append(df_events_send.loc[i, 'time'])
        if df_events_send.loc[i, 'disconnect'] == 2:
            send_disconnect_stop.append(df_events_send.loc[i, 'time'])
        if df_events_send.loc[i, 'reconnect'] == 1:
            send_reconnect_start.append(df_events_send.loc[i, 'time'])
        if df_events_send.loc[i, 'reconnect'] == 2:
            send_reconnect_stop.append(df_events_send.loc[i, 'time'])
    send_disconnect = list(zip(send_disconnect_start, send_disconnect_stop))
    send_reconnect = list(zip(send_reconnect_start, send_reconnect_stop))

    recv_disconnect_start = []
    recv_disconnect_stop = []
    recv_reconnect_start = []
    recv_reconnect_stop = []
    for i, row in df_events_recv.iterrows():
        if df_events_recv.loc[i, 'disconnect'] == 1:
            recv_disconnect_start.append(df_events_recv.loc[i, 'time'])
        if df_events_recv.loc[i, 'disconnect'] == 2:
            recv_disconnect_stop.append(df_events_recv.loc[i, 'time'])
        if df_events_recv.loc[i, 'reconnect'] == 1:
            recv_reconnect_start.append(df_events_recv.loc[i, 'time'])
        if df_events_recv.loc[i, 'reconnect'] == 2:
            recv_reconnect_stop.append(df_events_recv.loc[i, 'time'])
    recv_disconnect = list(zip(recv_disconnect_start, recv_disconnect_stop))
    recv_reconnect = list(zip(recv_reconnect_start, recv_reconnect_stop))

    fig = plt.figure()
    # set height ratios for subplots
    gs = gridspec.GridSpec(4, 1)

    # fig, ax = plt.subplots(4, 1, figsize=(10, 6))

    # the first subplot
    ax0 = plt.subplot(gs[0])

    # line1 = ax0.plot(df_signal_send['time'], df_signal_send['signal'], label='Measured by sender', marker='v',
    #                   color='tab:blue', linewidth=0)
    line11 = ax0.plot(df_signal_send['time'], df_signal_send['signal_avg'], label='Avg. rssi sender',
                      marker=',', color='tab:blue')
    ax0.yaxis.set_minor_locator(MultipleLocator(5))
    ax0.set_ylim(-95, -35)
    for i, j in send_disconnect:
        print("*** Send disconnect time: {}, {}".format(i, j))
        ax0.axvspan(i, j, ymin=0, ymax=0.5, color='#b8e1ff')
        ax0.axvline(x=i, ymax=0.5, color='tab:blue', linestyle=(0, (3, 5, 1, 5)))
        ax0.axvline(x=j, ymax=0.5, color='tab:blue', linestyle=(0, (3, 5, 1, 5)))
        if not noolsr:
            draw_brace_bottom(ax0, (i, j), "Sender:\nBS" r"$\rightarrow$" "MANET", '#006ab5')
        else:
            draw_brace_bottom(ax0, (i, j), "Sender:\nBS disconnect", '#006ab5')
    for i, j in send_reconnect:
        print("*** Send reconnect time: {}, {}".format(i, j))
        ax0.axvspan(i, j, ymin=0, ymax=0.5, color='#b8e1ff')
        ax0.axvline(x=i, ymax=0.5, color='tab:blue', linestyle=(0, (3, 5, 1, 5)))
        ax0.axvline(x=j, ymax=0.5, color='tab:blue', linestyle=(0, (3, 5, 1, 5)))
        if not noolsr:
            draw_brace_bottom(ax0, (i, j), "Sender:\nMANET" r"$\rightarrow$" "BS", '#006ab5')
        else:
            draw_brace_bottom(ax0, (i, j), "Sender:\nBS reconnect", '#006ab5')
    # line2 = ax0.plot(df_signal_recv['time'], df_signal_recv['signal'], label='Measured by receiver', marker='x',
    #                   color='tab:orange', linewidth=0)
    line22 = ax0.plot(df_signal_recv['time'], df_signal_recv['signal_avg'], label='Avg. rssi receiver',
                      marker=',', color='tab:orange', linestyle='dashed')
    for i, j in recv_disconnect:
        print("*** Recv disconnect time: {}, {}".format(i, j))
        ax0.axvspan(i, j, ymin=0.5, ymax=1, color='#ffcfa6')
        ax0.axvline(x=i, ymin=0.5, color='tab:orange', linestyle=(0, (3, 5, 1, 5, 1, 5)))
        ax0.axvline(x=j, ymin=0.5, color='tab:orange', linestyle=(0, (3, 5, 1, 5, 1, 5)))
        ymin, ymax = ax0.get_ylim()
        if not noolsr:
            draw_brace_top(ax0, (i, j), "Receiver:\nBS" r"$\rightarrow$" "MANET", '#ff7700')
        else:
            draw_brace_top(ax0, (i, j), "Receiver:\nBS disconnect", '#ff7700')
    for i, j in recv_reconnect:
        print("*** Recv reconnect time: {}, {}".format(i, j))
        ax0.axvspan(i, j, ymin=0.5, ymax=1, color='#ffcfa6')
        ax0.axvline(x=i, ymin=0.5, color='tab:orange', linestyle=(0, (3, 5, 1, 5, 1, 5)))
        ax0.axvline(x=j, ymin=0.5, color='tab:orange', linestyle=(0, (3, 5, 1, 5, 1, 5)))
        if not noolsr:
            draw_brace_top(ax0, (i, j), "Receiver:\nMANET" r"$\rightarrow$" "BS", '#ff7700')
        else:
            draw_brace_top(ax0, (i, j), "Receiver:\nBS reconnect", '#ff7700')

    # ax0.set_xlabel("Time (seconds)")
    ax0.set_xlabel("Time (min)")
    # ax0.set_ylabel("RSSI of AP (dBm)")
    ax0.set_ylabel("Base Station RSSI (dBm)")
    ax_top = ax0.twiny()
    ax0.legend(loc='upper center')
    # ax0.legend(loc='best', bbox_to_anchor=(0.4, 0.5, 0.2, 0.5))
    ax0.grid()

    # the second subplot
    # shared axis X
    ax1 = plt.subplot(gs[1])

    line0 = ax1.plot(df_time_series['time'], df_time_series['packet_loss'], label='Packet loss')
    # ax1.set_xlabel("Time (seconds)")
    ax1.set_xlabel("Time (min)")
    ax1.set_ylabel("Packet loss")
    # ax1.yaxis.set_major_locator(MultipleLocator(50))
    # ax1.yaxis.set_minor_locator(MultipleLocator(10))
    # ax1.set_ylim(-5, 200)
    # ax1.yaxis.set_major_locator(MultipleLocator(25))
    # ax1.yaxis.set_minor_locator(MultipleLocator(10))
    # ax1.set_ylim(-5, 110)
    ax1.yaxis.set_major_locator(MultipleLocator(150))
    ax1.yaxis.set_minor_locator(MultipleLocator(50))
    ax1.set_ylim(-20, 600)
    ax1.legend(loc='upper center')
    # remove last tick label
    yticks = ax1.yaxis.get_major_ticks()
    yticks[-1].label1.set_visible(False)
    ax1.grid()

    # the third subplot
    # shared axis X
    ax2 = plt.subplot(gs[2])

    line3 = ax2.plot(df_time_series['time'], df_time_series['latency'], label='Latency')
    lat_max = ax2.plot(df_time_series['time'],
                       np.zeros(len(df_time_series['time'])) + df_summary.loc[0, 'max_latency_s'],
                       label='Max. latency', linestyle='dashed')
    lat_avg = ax2.plot(df_time_series['time'],
                       np.zeros(len(df_time_series['time'])) + df_summary.loc[0, 'avg_latency_s'],
                       label='Avg. latency', linestyle='dotted')
    # ax3.set_xlabel("Time (seconds)")
    ax2.set_xlabel("Time (min)")
    ax2.set_ylabel("End-to-end Latency (seconds)")
    ax2.yaxis.set_minor_locator(MultipleLocator(0.1))
    # ax2.set_ylim(-0.1, 2.5)
    ax2.legend()
    # remove last tick label
    yticks = ax2.yaxis.get_major_ticks()
    yticks[-1].label1.set_visible(False)
    ax2.grid()

    # the fourth subplot
    # shared axis X
    ax3 = plt.subplot(gs[3])
    line3 = ax3.plot(df_time_series['time'], df_time_series['jitter'], label='Jitter')
    # lat_max = ax3.plot(df_time_series['time'], np.zeros(len(df_time_series['time'])) + df_summary.loc[0, 'max_latency_s'],
    #                     label='Max. latency', linestyle='dashed')
    # lat_avg = ax3.plot(df_time_series['time'],
    #                     np.zeros(len(df_time_series['time'])) + df_summary.loc[0, 'avg_latency_s'],
    #                     label='Avg. jitter', linestyle='dotted')
    # ax4.set_xlabel("Time (seconds)")
    ax3.set_xlabel("Time (min)")
    ax3.set_ylabel("Jitter (seconds)")
    ax3.yaxis.set_minor_locator(MultipleLocator(0.1))
    # ax3.set_ylim(-0.1, 2.5)
    ax3.legend()
    # remove last tick label for the second subplot
    yticks = ax3.yaxis.get_major_ticks()
    yticks[-1].label1.set_visible(False)
    ax3.grid()

    # for x in gs:
    #     x.set_xlim(0, 175)
    #     x.xaxis.set_major_locator(MultipleLocator(10))
    #     x.xaxis.set_major_formatter(FormatStrFormatter('%d'))
    #     x.xaxis.set_minor_locator(MultipleLocator(2.0))
    # ax_top.set_xlim(0, 175)
    # ax_top.xaxis.set_major_locator(MultipleLocator(10))
    # ax_top.xaxis.set_major_formatter(FormatStrFormatter('%d'))
    # ax_top.xaxis.set_minor_locator(MultipleLocator(2.0))

    # plt.rcParams.update({'font.size': 16})
    plt.tight_layout()
    # remove vertical gap between subplots
    plt.subplots_adjust(hspace=.0)
    if show:
        plt.show()
    else:
        plt.savefig(path + 'pendulum_olsr_no-qdisc_disconnect-88_reconnect-75_scaninterval-3.pdf')


def main(data_path, show, noolsr):
    summary_file = data_path + 'summary.csv'
    time_series_file = data_path + 'metrics_time_series.csv'
    buffer_file = data_path + 'sta1_buffer.csv'

    # read the csv files
    df_summary = pd.read_csv(summary_file, sep=',')
    df_time_series = pd.read_csv(time_series_file, sep=',')
    df_sender_buffer = pd.read_csv(buffer_file, sep=',')

    summary_columns = ['total_time_s', 'packet_sent', 'packet_received', 'packet_dropped', 'packet_dropped_rate',
                       'min_latency_s', 'max_latency_s', 'avg_latency_s', 'sd_latency_s', 'avg_jitter_s',
                       'sd_jitter_s', 'avg_packetrate_pkts', 'round']
    df_summary = df_summary[summary_columns]

    time_series_columns = ['time', 'latency', 'jitter', 'packet_loss']
    df_time_series = df_time_series[time_series_columns]

    buffer_columns = ['buffer_timestamp', 'data_throughput', 'pr4g_queue_occupancy', 'round']
    df_sender_buffer = df_sender_buffer[buffer_columns]

    # starting from time 0
    df_time_series['time'] = df_time_series['time'].apply(lambda x: x - df_time_series['time'].iloc[0])

    df_sender_buffer['buffer_timestamp'] = range(0,len(df_sender_buffer),1)


    df_packet_loss_peaks = df_time_series[
        (df_time_series.packet_loss > 0) & (df_time_series.packet_loss.shift(-1) == 0)].append(
        df_time_series.tail(1)[df_time_series.tail(1).packet_loss > 0])
    print("Packet loss peaks:\n", df_packet_loss_peaks)

    send_signal_file = data_path + 'sta1-wlan0_signal.csv'
    send_events_file = data_path + 'sta1_events.csv'
    recv_signal_file = data_path + 'sta3-wlan0_signal.csv'
    recv_events_file = data_path + 'sta3_events.csv'
    signal_columns = ["time", "SSID", "signal", "signal_avg", "rx_bitrate", "tx_bitrate"]
    events_columns = ['time', 'disconnect', 'reconnect', 'scanner_start', 'scanner_stop', 'scan_trigger']

    df_signal_send = pd.read_csv(send_signal_file, sep=',')
    df_events_send = pd.read_csv(send_events_file, sep=',')
    df_signal_recv = pd.read_csv(recv_signal_file, sep=',')
    df_events_recv = pd.read_csv(recv_events_file, sep=',')

    df_signal_send = df_signal_send[signal_columns]
    df_events_send = df_events_send[events_columns]
    df_signal_recv = df_signal_recv[signal_columns]
    df_events_recv = df_events_recv[events_columns]


    df_time_series['time'] = df_time_series['time'].apply(lambda x: x / 60)
    df_signal_send['time'] = df_signal_send['time'].apply(lambda x: x / 60)
    df_signal_recv['time'] = df_signal_recv['time'].apply(lambda x: x / 60)
    df_events_send['time'] = df_events_send['time'].apply(lambda x: x / 60)
    df_events_recv['time'] = df_events_recv['time'].apply(lambda x: x / 60)
    df_sender_buffer['buffer_timestamp'] = df_sender_buffer['buffer_timestamp'].apply(lambda x: x / 60)

    send_disconnect_start = []
    send_disconnect_stop = []
    send_reconnect_start = []
    send_reconnect_stop = []
    for i, row in df_events_send.iterrows():
        if df_events_send.loc[i, 'disconnect'] == 1:
            send_disconnect_start.append(df_events_send.loc[i, 'time'])
        if df_events_send.loc[i, 'disconnect'] == 2:
            send_disconnect_stop.append(df_events_send.loc[i, 'time'])
        if df_events_send.loc[i, 'reconnect'] == 1:
            send_reconnect_start.append(df_events_send.loc[i, 'time'])
        if df_events_send.loc[i, 'reconnect'] == 2:
            send_reconnect_stop.append(df_events_send.loc[i, 'time'])
    send_disconnect = list(zip(send_disconnect_start, send_disconnect_stop))
    send_reconnect = list(zip(send_reconnect_start, send_reconnect_stop))

    recv_disconnect_start = []
    recv_disconnect_stop = []
    recv_reconnect_start = []
    recv_reconnect_stop = []
    for i, row in df_events_recv.iterrows():
        if df_events_recv.loc[i, 'disconnect'] == 1:
            recv_disconnect_start.append(df_events_recv.loc[i, 'time'])
        if df_events_recv.loc[i, 'disconnect'] == 2:
            recv_disconnect_stop.append(df_events_recv.loc[i, 'time'])
        if df_events_recv.loc[i, 'reconnect'] == 1:
            recv_reconnect_start.append(df_events_recv.loc[i, 'time'])
        if df_events_recv.loc[i, 'reconnect'] == 2:
            recv_reconnect_stop.append(df_events_recv.loc[i, 'time'])
    recv_disconnect = list(zip(recv_disconnect_start, recv_disconnect_stop))
    recv_reconnect = list(zip(recv_reconnect_start, recv_reconnect_stop))

    #fig, ax = plt.subplots(4, 1, figsize=(6, 4), sharex=True)
    #fig, ax = plt.subplots(4, 1, sharex='col', sharey='row', gridspec_kw={'hspace': 0, 'wspace': 0})

    # create a group of prot, and remove vertical gap between subplots
    fig, ax = plt.subplots(5, 1, sharex='col', gridspec_kw={'hspace': 0, 'wspace': 0},tight_layout=True)



    line1 = ax[0].plot(df_signal_send['time'], df_signal_send['signal'],marker='v', #label='Sender',
                       color='tab:blue', linewidth=0, markersize=0.5)
    line11 = ax[0].plot(df_signal_send['time'], df_signal_send['signal_avg'], label='Sender',
                        marker=',', color='tab:blue')
    #ax[0].yaxis.set_minor_locator(MultipleLocator(5))
    ax[0].set_ylim(-95, -35)
    for i, j in send_disconnect:
        print("*** Send disconnect time: {}, {}".format(i, j))
        ax[0].axvspan(i, j, ymin=0, ymax=0.5, color='#b8e1ff')
        ax[0].axvline(x=i, ymax=0.5, color='tab:blue', linestyle=(0, (3, 5, 1, 5)))
        ax[0].axvline(x=j, ymax=0.5, color='tab:blue', linestyle=(0, (3, 5, 1, 5)))
        if not noolsr:
            #draw_brace_bottom(ax[0], (i, j), "BS" r"$\rightarrow$" "MANET", '#006ab5')

            ax[0].annotate("BS" r"$\rightarrow$" "MANET", fontsize=9,  color='#006ab5',
                        xy=(i, -80), xycoords='data',textcoords='offset points', xytext=(20, 0),
                        #bbox=dict(boxstyle="round", fc="0.8"),
                        arrowprops=dict(arrowstyle="->", color='#006ab5'))
        else:
            #draw_brace_bottom(ax[0], (i, j), "BS disconnect", '#006ab5')

            ax[0].annotate("BS disconnect", fontsize=9,  color='#006ab5',
                        xy=(i, -80), xycoords='data',textcoords='offset points', xytext=(20, 0),
                        #bbox=dict(boxstyle="round", fc="0.8"),
                        arrowprops=dict(arrowstyle="->", color='#006ab5'))

    for i, j in send_reconnect:
        print("*** Send reconnect time: {}, {}".format(i, j))
        ax[0].axvspan(i, j, ymin=0, ymax=0.5, color='#b8e1ff')
        ax[0].axvline(x=i, ymax=0.5, color='tab:blue', linestyle=(0, (3, 5, 1, 5)))
        ax[0].axvline(x=j, ymax=0.5, color='tab:blue', linestyle=(0, (3, 5, 1, 5)))
        if not noolsr:
            #draw_brace_bottom(ax[0], (i, j), "MANET" r"$\rightarrow$" "BS", '#006ab5')

            ax[0].annotate("MANET" r"$\rightarrow$" "BS", fontsize=9,  color='#006ab5',
                        xy=(i, -80), xycoords='data',textcoords='offset points', xytext=(-70, 10),
                        #bbox=dict(boxstyle="round", fc="0.8"),
                        arrowprops=dict(arrowstyle="->", color='#006ab5'))
        else:
            #draw_brace_bottom(ax[0], (i, j), "BS reconnect", '#006ab5')

            ax[0].annotate("BS reconnect", fontsize=9,  color='#006ab5',
                        xy=(i, -80), xycoords='data',textcoords='offset points', xytext=(-70, 10),
                        #bbox=dict(boxstyle="round", fc="0.8"),
                        arrowprops=dict(arrowstyle="->", color='#006ab5'))
    line2 = ax[0].plot(df_signal_recv['time'], df_signal_recv['signal'], marker='x',# label='Receiver',
                       color='tab:orange', linewidth=0, markersize=0.5)
    line22 = ax[0].plot(df_signal_recv['time'], df_signal_recv['signal_avg'], label='Receiver',
                        marker=',', color='tab:orange', linestyle='dashed')
    for i, j in recv_disconnect:
        print("*** Recv disconnect time: {}, {}".format(i, j))
        ax[0].axvspan(i, j, ymin=0.5, ymax=1, color='#ffcfa6')
        ax[0].axvline(x=i, ymin=0.5, color='tab:orange', linestyle=(0, (3, 5, 1, 5, 1, 5)))
        ax[0].axvline(x=j, ymin=0.5, color='tab:orange', linestyle=(0, (3, 5, 1, 5, 1, 5)))
        ymin, ymax = ax[0].get_ylim()
        if not noolsr:
            #draw_brace_top(ax[0], (i, j), "BS" r"$\rightarrow$" "MANET", '#ff7700')

            ax[0].annotate("BS" r"$\rightarrow$" "MANET", fontsize=9,  color='#ff7700',
                        xy=(i, -50), xycoords='data',textcoords='offset points', xytext=(-70, 4),
                        #bbox=dict(boxstyle="round", fc="0.8"),
                        arrowprops=dict(arrowstyle="->", color='#ff7700'))
        else:
            #draw_brace_top(ax[0], (i, j), "BS disconnect", '#ff7700')

            ax[0].annotate("BS disconnect", fontsize=9, color='#ff7700',
                           xy=(i, -50), xycoords='data',textcoords='offset points', xytext=(-70, 4),
                           # bbox=dict(boxstyle="round", fc="0.8"),
                           arrowprops=dict(arrowstyle="->", color='#ff7700'))
    for i, j in recv_reconnect:
        print("*** Recv reconnect time: {}, {}".format(i, j))
        ax[0].axvspan(i, j, ymin=0.5, ymax=1, color='#ffcfa6')
        ax[0].axvline(x=i, ymin=0.5, color='tab:orange', linestyle=(0, (3, 5, 1, 5, 1, 5)))
        ax[0].axvline(x=j, ymin=0.5, color='tab:orange', linestyle=(0, (3, 5, 1, 5, 1, 5)))
        if not noolsr:
            #draw_brace_top(ax[0], (i, j), "MANET" r"$\rightarrow$" "BS", '#ff7700')

            ax[0].annotate("MANET" r"$\rightarrow$" "BS", fontsize=9, color='#ff7700',
                           xy=(i, -50), xycoords='data',textcoords='offset points', xytext=(-70, 4),
                           # bbox=dict(boxstyle="round", fc="0.8"),
                           arrowprops=dict(arrowstyle="->", color='#ff7700'))
        else:
            #draw_brace_top(ax[0], (i, j), "BS reconnect", '#ff7700')

            ax[0].annotate("BS reconnect", fontsize=9, color='#ff7700',
                           xy=(i, -50), xycoords='data',textcoords='offset points', xytext=(-70, 4),
                           # bbox=dict(boxstyle="round", fc="0.8"),
                           arrowprops=dict(arrowstyle="->", color='#ff7700'))

    # ax[0].set_xlabel("Time (seconds)")
    #ax[0].set_xlabel("Time (min)")
    # ax[0].set_ylabel("RSSI of AP (dBm)")
    ax[0].set_ylabel("BS RSSI\n(dBm)")
    # ax_top = ax[0].twiny()
    ax[0].legend(loc='best')#'upper center')
    # ax[0].legend(loc='best', bbox_to_anchor=(0.4, 0.5, 0.2, 0.5))
    ax[0].grid()


    line0 = ax[1].plot(df_sender_buffer['buffer_timestamp'], df_sender_buffer['pr4g_queue_occupancy'], label='Buffer occupancy', color='k')
    ax[1].set_ylabel("Buffer\n(%)")
    ax[1].grid()
    yticks = ax[1].yaxis.get_major_ticks()
    yticks[-1].label1.set_visible(False)



    line1 = ax[2].plot(df_time_series['time'], df_time_series['packet_loss'], label='Packet loss',color='k')
    # ax[2].set_xlabel("Time (seconds)")
    #ax[2].set_xlabel("Time (min)")
    ax[2].set_ylabel("Packet\nloss")
    # ax[2].yaxis.set_major_locator(MultipleLocator(50))
    # ax[2].yaxis.set_minor_locator(MultipleLocator(10))
    # ax[2].set_ylim(-5, 200)
    # ax[2].yaxis.set_major_locator(MultipleLocator(25))
    # ax[2].yaxis.set_minor_locator(MultipleLocator(10))
    # ax[2].set_ylim(-5, 110)
    #ax[2].yaxis.set_major_locator(MultipleLocator(150))
    #ax[2].yaxis.set_minor_locator(MultipleLocator(50))
    # ax[2].set_ylim(-20, 600)
    #ax[2].legend(loc='best')
    ax[2].grid()
    yticks = ax[2].yaxis.get_major_ticks()
    yticks[-1].label1.set_visible(False)

    line3 = ax[3].plot(df_time_series['time'], df_time_series['latency'],color='k')#, label='Latency')
    # lat_max = ax[3].plot(df_time_series['time'], np.zeros(len(df_time_series['time'])) + df_summary.loc[0, 'max_latency_s'],
    #                     label='Max. latency', linestyle='dashed')
    # lat_avg = ax[3].plot(df_time_series['time'],
    #                     np.zeros(len(df_time_series['time'])) + df_summary.loc[0, 'avg_latency_s'],
    #                     label='Avg. latency', linestyle='dotted')
    # ax[3].set_xlabel("Time (seconds)")
    ax[3].set_xlabel("Time (min)")
    ax[3].set_ylabel("Latency\n(sec)")
    #ax[3].yaxis.set_minor_locator(MultipleLocator(0.1))
    #ax[3].set_ylim(-0.1, 2.5)
    #ax[3].legend(loc='best')
    ax[3].grid()
    yticks = ax[3].yaxis.get_major_ticks()
    yticks[-1].label1.set_visible(False)

    line3 = ax[4].plot(df_time_series['time'], df_time_series['jitter'],color='k', label='Jitter')
    # ax[4].set_xlabel("Time (seconds)")
    ax[4].set_xlabel("Time (min)")
    ax[4].set_ylabel("Jitter\n(sec)")
    #ax[4].yaxis.set_minor_locator(MultipleLocator(0.1))
    #ax[4].set_ylim(-0.1, 2.5)
    #ax[4].legend(loc='best')
    ax[4].grid()
    yticks = ax[4].yaxis.get_major_ticks()
    yticks[-1].label1.set_visible(False)

    #for x in ax:
    #    x.set_xlim(0,int(np.max(df_time_series['time'])))
    #    x.xaxis.set_major_locator(MultipleLocator(10))
    #    x.xaxis.set_major_formatter(FormatStrFormatter('%d'))
    #    x.xaxis.set_minor_locator(MultipleLocator(2.0))
    # ax_top.set_xlim(0, 175)
    # ax_top.xaxis.set_major_locator(MultipleLocator(10))
    # ax_top.xaxis.set_major_formatter(FormatStrFormatter('%d'))
    # ax_top.xaxis.set_minor_locator(MultipleLocator(2.0))

    fig.align_labels()  # same as fig.align_xlabels(); fig.align_ylabels()
    # plt.rcParams.update({'font.size': 16})
    if show:
        plt.show()
    else:
        plt.savefig(path + 'pendulum_olsr_no-qdisc_disconnect-88_reconnect-75_scaninterval-3.pdf')


def draw_brace_top(ax, xspan, text, color):
    """Draws an annotated brace above the diagram."""
    xmin, xmax = xspan
    xspan = xmax - xmin
    ymin, ymax = ax.get_ylim()
    yspan = ymax - ymin
    if xspan < 3:
        x = np.full(2, xmin + (xspan / 2))
        y = np.array([ymax - .01 * yspan, ymax + .23 * yspan])
        ax.plot(x, y, color=color, lw=1, clip_on=False)
    else:
        ax_xmin, ax_xmax = ax.get_xlim()
        xax_span = ax_xmax - ax_xmin
        resolution = int(xspan / xax_span * 100) * 2 + 1  # guaranteed uneven
        beta = 800. / xax_span  # the higher this is, the smaller the radius

        x = np.linspace(xmin, xmax, resolution)
        x_half = x[:resolution // 2 + 1]
        y_half_brace = (1 / (1. + np.exp(-beta * (x_half - x_half[0])))
                        + 1 / (1. + np.exp(-beta * (x_half - x_half[-1]))))
        y = np.concatenate((y_half_brace, y_half_brace[-2::-1]))
        y = ymax + (.05 * y + .15) * yspan  # adjust vertical position

        ax.autoscale(False)
        ax.plot(x, y, color=color, lw=1, clip_on=False)
    ax.text((xmax + xmin) / 2., ymax + .25 * yspan, text, color=color, ha='center', va='bottom')


def draw_brace_bottom(ax, xspan, text, color):
    """Draws an annotated brace below the diagram."""
    xmin, xmax = xspan
    xspan = xmax - xmin
    ymin, ymax = ax.get_ylim()
    yspan = ymax - ymin
    if xspan < 3:
        x = np.full(2, xmin + (xspan / 2))
        y = np.array([ymin - .23 * yspan, ymin + .01 * yspan])
        ax.plot(x, y, color=color, lw=1, clip_on=False)
    else:
        ax_xmin, ax_xmax = ax.get_xlim()
        xax_span = ax_xmax - ax_xmin
        resolution = int(xspan / xax_span * 100) * 2 + 1  # guaranteed uneven
        beta = 800. / xax_span  # the higher this is, the smaller the radius

        x = np.linspace(xmin, xmax, resolution)
        x_half = x[:resolution // 2 + 1]
        y_half_brace = (1 / (1. + np.exp(-beta * (x_half - x_half[0])))
                        + 1 / (1. + np.exp(-beta * (x_half - x_half[-1]))))
        y = np.concatenate((y_half_brace, y_half_brace[-2::-1]))
        y = ymin - (.05 * y + .15) * yspan  # adjust vertical position

        ax.autoscale(False)
        ax.plot(x, y, color=color, lw=1, clip_on=False)
    ax.text((xmax + xmin) / 2., ymin - .25 * yspan, text, color=color, ha='center', va='top')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Tactical network experiment!")
    parser.add_argument("-d", "--directory", help="Directory of log files", type=str, required=True)
    parser.add_argument("-s", "--show", help="Show the plot instead of saving to file", action="store_true",
                        default=False)
    parser.add_argument("-O", "--noolsr", help="No olsr when connection to BS is lost (default: False)",
                        action='store_true', default=False)
    args = parser.parse_args()
    path = args.directory
    main(path, args.show, args.noolsr)
