import argparse
import os
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def main(data_path, show, noOlsr, file_name, short):
    summary_file = data_path + 'summary.csv'
    time_series_file = data_path + 'metrics_time_series.csv'
    buffer_file = data_path + 'sta1_buffer.csv'

    # read the csv files
    df_summary = pd.read_csv(summary_file, sep=',')
    df_time_series = pd.read_csv(time_series_file, sep=',')
    df_sender_buffer = pd.read_csv(buffer_file, sep=',')

    summary_columns = ['total_time_s', 'packet_sent', 'packet_received', 'packet_dropped', 'packet_dropped_rate',
                       'min_latency_s', 'max_latency_s', 'avg_latency_s', 'sd_latency_s', 'avg_jitter_s',
                       'sd_jitter_s', 'avg_bitrate', 'sd_bitrate', 'avg_packetrate_pkts', 'round']
    df_summary = df_summary[summary_columns]

    time_series_columns = ['time', 'bitrate', 'latency', 'jitter', 'packet_loss']
    df_time_series = df_time_series[time_series_columns]

    buffer_columns = ['buffer_timestamp', 'data_throughput', 'pr4g_queue_occupancy', 'round']
    df_sender_buffer = df_sender_buffer[buffer_columns]
    df_sender_buffer['data_throughput'] = df_sender_buffer['data_throughput'].str.replace('K', '')
    df_sender_buffer['data_throughput'] = df_sender_buffer['data_throughput'].astype(float)

    # converting bitrate to Kbit rate
    df_time_series['bitrate'] = df_time_series['bitrate'].apply(lambda x: x / 1000)

    # starting from time 0
    df_time_series['time'] = df_time_series['time'].apply(lambda x: x - df_time_series['time'].iloc[0])

    df_sender_buffer['buffer_timestamp'] = range(0, len(df_sender_buffer), 1)

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

    # df_signal_send = pd.read_csv(send_signal_file, sep=',')
    # df_signal_recv = pd.read_csv(recv_signal_file, sep=',')

    # df_signal_send = df_signal_send[signal_columns]
    # df_signal_recv = df_signal_recv[signal_columns]

    df_time_series['time'] = df_time_series['time'].apply(lambda x: x / 60)
    # df_signal_send['time'] = df_signal_send['time'].apply(lambda x: x / 60)
    # df_signal_recv['time'] = df_signal_recv['time'].apply(lambda x: x / 60)
    df_sender_buffer['buffer_timestamp'] = df_sender_buffer['buffer_timestamp'].apply(lambda x: x / 60)

    if os.path.isfile(send_events_file):

        df_events_send = pd.read_csv(send_events_file, sep=',')
        df_events_recv = pd.read_csv(recv_events_file, sep=',')

        df_events_send = df_events_send[events_columns]
        df_events_recv = df_events_recv[events_columns]

        df_events_send['time'] = df_events_send['time'].apply(lambda x: x / 60)
        df_events_recv['time'] = df_events_recv['time'].apply(lambda x: x / 60)

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

    # applying SMA
    df_time_series['bitrate'] = df_time_series.bitrate.rolling(20).mean()
    # df_time_series['latency'] = df_time_series.latency.rolling(5).mean()
    # df_time_series['jitter'] = df_time_series.jitter.rolling(5).mean()

    #short = True
    if short:
        # fig, ax = plt.subplots(4, 1, figsize=(6, 4), sharex=True)
        fig, ax = plt.subplots(4, 1, sharex='col', figsize=(6, 3), gridspec_kw={'hspace': 0, 'wspace': 0},
                               tight_layout=True)
    else:
        # create a group of plot, and remove vertical gap between subplots
        fig, ax = plt.subplots(6, 1, sharex='col', figsize=(6, 5), gridspec_kw={'hspace': 0.0, 'wspace': 0},
                               tight_layout=True)

    # fig, ax = plt.subplots(6, 1, sharex='col', gridspec_kw={'hspace': 0.0, 'wspace': 0}, tight_layout=True)
    # fig.set_size_inches(6, 5)

    # line0 = ax[0].plot(df_signal_send['time'], df_signal_send['signal'], marker='v',  # label='Sender',
    #                    color='tab:blue', linewidth=0, markersize=0.5)
    # line01 = ax[0].plot(df_signal_send['time'], df_signal_send['signal_avg'], label='Sender',
    #                     marker=',', color='tab:blue')

    if os.path.isfile(send_events_file):
        for i, j in send_disconnect:
            print("*** Send disconnect time: {}, {}".format(i, j))
            ax[0].axvspan(i, j, ymin=0, ymax=0.5, color='#b8e1ff')
            ax[0].axvline(x=i, ymax=0.5, color='tab:blue', linestyle=(0, (3, 5, 1, 5)))
            ax[0].axvline(x=j, ymax=0.5, color='tab:blue', linestyle=(0, (3, 5, 1, 5)))
            if not noOlsr:
                # draw_brace_bottom(ax[0], (i, j), "CP"  r"$\rightarrow$" "MN", '#006ab5')

                ax[0].annotate("CP"  r"$\rightarrow$" "MN", fontsize=9, color='#006ab5',
                               xy=(i, -85), xycoords='data', textcoords='offset points', xytext=(20, 0),
                               # bbox=dict(boxstyle="round", fc="0.8"),
                               arrowprops=dict(arrowstyle="->", color='#006ab5'))
            else:
                # draw_brace_bottom(ax[0], (i, j), "BS disconnect", '#006ab5')

                ax[0].annotate("CP discon", fontsize=9, color='#006ab5',
                               xy=(i, -85), xycoords='data', textcoords='offset points', xytext=(20, 0),
                               # bbox=dict(boxstyle="round", fc="0.8"),
                               arrowprops=dict(arrowstyle="->", color='#006ab5'))

        for i, j in send_reconnect:
            print("*** Send reconnect time: {}, {}".format(i, j))
            ax[0].axvspan(i, j, ymin=0, ymax=0.5, color='#b8e1ff')
            ax[0].axvline(x=i, ymax=0.5, color='tab:blue', linestyle=(0, (3, 5, 1, 5)))
            ax[0].axvline(x=j, ymax=0.5, color='tab:blue', linestyle=(0, (3, 5, 1, 5)))
            if not noOlsr:
                # draw_brace_bottom(ax[0], (i, j), "MN" r"$\rightarrow$" "CP" , '#006ab5')

                ax[0].annotate("MN" r"$\rightarrow$" "CP", fontsize=9, color='#006ab5',
                               xy=(i, -85), xycoords='data', textcoords='offset points', xytext=(-70, 0),
                               # bbox=dict(boxstyle="round", fc="0.8"),
                               arrowprops=dict(arrowstyle="->", color='#006ab5'))
            else:
                # draw_brace_bottom(ax[0], (i, j), "CP reconnect", '#006ab5')

                ax[0].annotate("CP recon", fontsize=9, color='#006ab5',
                               xy=(i, -85), xycoords='data', textcoords='offset points', xytext=(-70, 0),
                               # bbox=dict(boxstyle="round", fc="0.8"),
                               arrowprops=dict(arrowstyle="->", color='#006ab5'))

    # line02 = ax[0].plot(df_signal_recv['time'], df_signal_recv['signal'], marker='x',  # label='Receiver',
    #                     color='tab:orange', linewidth=0, markersize=0.5)
    # line03 = ax[0].plot(df_signal_recv['time'], df_signal_recv['signal_avg'], label='Receiver',
    #                     marker=',', color='tab:orange', linestyle='dashed')

    if os.path.isfile(send_events_file):
        for i, j in recv_disconnect:
            print("*** Recv disconnect time: {}, {}".format(i, j))
            ax[0].axvspan(i, j, ymin=0.5, ymax=1, color='#ffcfa6')
            ax[0].axvline(x=i, ymin=0.5, color='tab:orange', linestyle=(0, (3, 5, 1, 5, 1, 5)))
            ax[0].axvline(x=j, ymin=0.5, color='tab:orange', linestyle=(0, (3, 5, 1, 5, 1, 5)))
            ymin, ymax = ax[0].get_ylim()
            if not noOlsr:
                # draw_brace_top(ax[0], (i, j), "CP"  r"$\rightarrow$" "MN", '#ff7700')

                ax[0].annotate("CP"  r"$\rightarrow$" "MN", fontsize=9, color='#ff7700',
                               xy=(i, -75), xycoords='data', textcoords='offset points', xytext=(20, 0),
                               # bbox=dict(boxstyle="round", fc="0.8"),
                               arrowprops=dict(arrowstyle="->", color='#ff7700'))
            else:
                # draw_brace_top(ax[0], (i, j), "CP disconnect", '#ff7700')

                ax[0].annotate("CP discon", fontsize=9, color='#ff7700',
                               xy=(i, -75), xycoords='data', textcoords='offset points', xytext=(20, 0),
                               # bbox=dict(boxstyle="round", fc="0.8"),
                               arrowprops=dict(arrowstyle="->", color='#ff7700'))
        for i, j in recv_reconnect:
            print("*** Recv reconnect time: {}, {}".format(i, j))
            ax[0].axvspan(i, j, ymin=0.5, ymax=1, color='#ffcfa6')
            ax[0].axvline(x=i, ymin=0.5, color='tab:orange', linestyle=(0, (3, 5, 1, 5, 1, 5)))
            ax[0].axvline(x=j, ymin=0.5, color='tab:orange', linestyle=(0, (3, 5, 1, 5, 1, 5)))
            if not noOlsr:
                # draw_brace_top(ax[0], (i, j), "MN" r"$\rightarrow$" "CP" , '#ff7700')

                ax[0].annotate("MN" r"$\rightarrow$" "CP", fontsize=9, color='#ff7700',
                               xy=(i, -75), xycoords='data', textcoords='offset points', xytext=(-70, 0),
                               # bbox=dict(boxstyle="round", fc="0.8"),
                               arrowprops=dict(arrowstyle="->", color='#ff7700'))
            else:
                # draw_brace_top(ax[0], (i, j), "CP reconnect", '#ff7700')

                ax[0].annotate("CP recon", fontsize=9, color='#ff7700',
                               xy=(i, -75), xycoords='data', textcoords='offset points', xytext=(-70, 0),
                               # bbox=dict(boxstyle="round", fc="0.8"),
                               arrowprops=dict(arrowstyle="->", color='#ff7700'))

    # ax[0].set_xlabel("Time (seconds)")
    # ax[0].set_xlabel("Time (min)")
    # ax[0].set_ylabel("RSSI of AP (dBm)")
    ax[0].set_ylabel("CP RSSI\n(dBm)")
    # ax_top = ax[0].twiny()
    # ax[0].legend(loc='upper center')#'upper center')
    ax[0].legend(bbox_to_anchor=(0., 1.02, 1., .102), loc='lower center', columnspacing=0.5, borderaxespad=0.,
                 fontsize=10, ncol=2, handletextpad=0.5, fancybox=False, shadow=False)
    # ax[0].legend(loc='best', bbox_to_anchor=(0.4, 0.5, 0.2, 0.5))
    ax[0].grid(color='gray', linestyle='dashed', lw=0.5)
    # ax[0].yaxis.set_minor_locator(MultipleLocator(5))

    # ax[0].set_ylim(-95, -30)

    line1 = ax[1].plot(df_time_series['time'], df_time_series['bitrate'], linewidth=1.5, label='DR', color='tab:orange')
    ax[1].set_ylabel("DR\n(Kbit/s)")
    ax[1].grid(color='gray', linestyle='dashed', lw=0.5)
    yticks = ax[1].yaxis.get_major_ticks()
    yticks[-1].label1.set_visible(False)

    # line1 = ax[1].plot(df_sender_buffer['buffer_timestamp'], df_sender_buffer['data_throughput'], linewidth=1.5, label='DR', color='tab:orange')
    # ax[1].set_ylabel("Radio DR\n(Kbit/s)")
    # ax[1].grid(color='gray', linestyle='dashed', lw = 0.5)
    # yticks = ax[1].yaxis.get_major_ticks()
    # yticks[-1].label1.set_visible(False)

    line2 = ax[2].plot(df_sender_buffer['buffer_timestamp'], df_sender_buffer['pr4g_queue_occupancy'], linewidth=1.5,
                       label='Buffer occupancy', color='tab:blue')
    ax[2].set_ylabel("Buffer\n(%)")
    ax[2].grid(color='gray', linestyle='dashed', lw=0.5)
    yticks = ax[2].yaxis.get_major_ticks()
    yticks[-1].label1.set_visible(False)

    line3 = ax[3].plot(df_time_series['time'], df_time_series['packet_loss'], linewidth=1.5, label='Packet loss',
                       color='tab:orange')
    # ax[3].set_xlabel("Time (seconds)")
    if short:
        ax[3].set_xlabel("Time (min)")
    ax[3].set_ylabel("Packet\nloss")
    # ax[3].yaxis.set_major_locator(MultipleLocator(50))
    # ax[3].yaxis.set_minor_locator(MultipleLocator(10))
    # ax[3].set_ylim(-5, 200)
    # ax[3].yaxis.set_major_locator(MultipleLocator(25))
    # ax[3].yaxis.set_minor_locator(MultipleLocator(10))
    # ax[3].set_ylim(-5, 110)
    # ax[3].yaxis.set_major_locator(MultipleLocator(150))
    # ax[3].yaxis.set_minor_locator(MultipleLocator(50))
    # ax[3].set_ylim(-20, 600)
    # ax[3].legend(loc='best')
    ax[3].grid(color='gray', linestyle='dashed', lw=0.5)
    yticks = ax[3].yaxis.get_major_ticks()
    yticks[-1].label1.set_visible(False)

    if not short:
        line4 = ax[4].plot(df_time_series['time'], df_time_series['latency'], linewidth=1.5,
                           color='tab:orange')  # , label='Latency')
        # lat_max = ax[4].plot(df_time_series['time'], np.zeros(len(df_time_series['time'])) + df_summary.loc[0, 'max_latency_s'],
        #                     label='Max. latency', linestyle='dashed')
        # lat_avg = ax[4].plot(df_time_series['time'],
        #                     np.zeros(len(df_time_series['time'])) + df_summary.loc[0, 'avg_latency_s'],
        #                     label='Avg. latency', linestyle='dotted')
        # ax[4].set_xlabel("Time (seconds)")
        ax[4].set_xlabel("Time (min)")
        ax[4].set_ylabel("Latency\n(sec)")
        # ax[4].yaxis.set_minor_locator(MultipleLocator(0.1))
        # ax[4].set_ylim(-0.1, 2.5)
        # ax[4].legend(loc='best')
        ax[4].grid(color='gray', linestyle='dashed', lw=0.5)
        yticks = ax[4].yaxis.get_major_ticks()
        yticks[-1].label1.set_visible(False)

        line5 = ax[5].plot(df_time_series['time'], df_time_series['jitter'], linewidth=1.5, color='tab:orange',
                           label='Jitter')
        # ax[5].set_xlabel("Time (seconds)")
        ax[5].set_xlabel("Time (min)")
        ax[5].set_ylabel("Jitter\n(sec)")
        # ax[5].yaxis.set_minor_locator(MultipleLocator(0.1))
        # ax[5].set_ylim(-0.1, 2.5)
        # ax[5].legend(loc='best')
        ax[5].grid(color='gray', linestyle='dashed', lw=0.5)
        yticks = ax[5].yaxis.get_major_ticks()
        yticks[-1].label1.set_visible(False)

    # for x in ax:
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
        if not noOlsr:
            plt.savefig(path + file_name.replace('.csv', '_olsr.pdf'))  # , bbox_inches='tight', dpi=200)
            # plt.savefig(path + 'pendulum_olsr_disconnect-88_reconnect-75_scaninterval-3.pdf')
        else:
            plt.savefig(path + file_name.replace('.csv', '_no-olsr.pdf'))  # , bbox_inches='tight', dpi=200)
            # plt.savefig(path + 'pendulum_no-olsr.pdf')


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
    parser.add_argument("-O", "--noOlsr", help="No olsr when connection to Command Post (CP) is lost (default: False)",
                        action='store_true', default=False)
    parser.add_argument("-short", "--short", help="Short plot removes latency and jitter metrics (default: False)",
                        action='store_true', default=True, required=False)
    parser.add_argument("-f", "--fileName", help="File name for the plots", type=str, required=True)

    args = parser.parse_args()
    path = args.directory
    main(path, args.show, args.noOlsr, args.fileName, args.short)
