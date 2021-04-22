import argparse

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from matplotlib.ticker import MultipleLocator, FormatStrFormatter


def main(data_path, show, noolsr):
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

    fig, ax = plt.subplots(3, 1, figsize=(12, 8))

    line1 = ax[0].plot(df_signal_send['time'], df_signal_send['signal'], label='Signal strength sender', marker='v',
                       color='tab:blue', linewidth=0)
    line11 = ax[0].plot(df_signal_send['time'], df_signal_send['signal_avg'], label='Signal strength sender moving avg.',
                        marker=',', color='tab:blue')
    ax[0].yaxis.set_minor_locator(MultipleLocator(5))
    ax[0].set_ylim(-100, -30)
    for i, j in send_disconnect:
        print("*** Send disconnect time: {}, {}".format(i, j))
        ax[0].axvspan(i, j, ymin=0, ymax=0.5, color='#b8e1ff')
        ax[0].axvline(x=i, ymax=0.5, color='tab:blue', linestyle=(0, (3, 5, 1, 5)))
        ax[0].axvline(x=j, ymax=0.5, color='tab:blue', linestyle=(0, (3, 5, 1, 5)))
        ymin, ymax = ax[0].get_ylim()
        if not noolsr:
            draw_brace_bottom(ax[0], (i, j), "Sender:\nAP" r"$\rightarrow$" "OLSR", '#006ab5')
        else:
            draw_brace_bottom(ax[0], (i, j), "Sender:\nAP disconnect", '#006ab5')
    for i, j in send_reconnect:
        print("*** Send reconnect time: {}, {}".format(i, j))
        ax[0].axvspan(i, j, ymin=0, ymax=0.5, color='#b8e1ff')
        ax[0].axvline(x=i, ymax=0.5, color='tab:blue', linestyle=(0, (3, 5, 1, 5)))
        ax[0].axvline(x=j, ymax=0.5, color='tab:blue', linestyle=(0, (3, 5, 1, 5)))
        if not noolsr:
            draw_brace_bottom(ax[0], (i, j), "Sender:\nOLSR" r"$\rightarrow$" "AP", '#006ab5')
        else:
            draw_brace_bottom(ax[0], (i, j), "Sender:\nAP reconnect", '#006ab5')
    line2 = ax[0].plot(df_signal_recv['time'], df_signal_recv['signal'], label='Signal strength receiver', marker='x',
                       color='tab:orange', linewidth=0)
    line22 = ax[0].plot(df_signal_recv['time'], df_signal_recv['signal_avg'], label='Signal strength receiver moving avg.',
                        marker=',', color='tab:orange', linestyle='dashed')
    for i, j in recv_disconnect:
        print("*** Recv disconnect time: {}, {}".format(i, j))
        ax[0].axvspan(i, j, ymin=0.5, ymax=1, color='#ffcfa6')
        ax[0].axvline(x=i, ymin=0.5, color='tab:orange', linestyle=(0, (3, 5, 1, 5, 1, 5)))
        ax[0].axvline(x=j, ymin=0.5, color='tab:orange', linestyle=(0, (3, 5, 1, 5, 1, 5)))
        ymin, ymax = ax[0].get_ylim()
        if not noolsr:
            draw_brace_top(ax[0], (i, j), "Receiver:\nAP" r"$\rightarrow$" "OLSR", '#ff7700')
        else:
            draw_brace_top(ax[0], (i, j), "Receiver:\nAP disconnect", '#ff7700')
    for i, j in recv_reconnect:
        print("*** Recv reconnect time: {}, {}".format(i, j))
        ax[0].axvspan(i, j, ymin=0.5, ymax=1, color='#ffcfa6')
        ax[0].axvline(x=i, ymin=0.5, color='tab:orange', linestyle=(0, (3, 5, 1, 5, 1, 5)))
        ax[0].axvline(x=j, ymin=0.5, color='tab:orange', linestyle=(0, (3, 5, 1, 5, 1, 5)))
        if not noolsr:
            draw_brace_top(ax[0], (i, j), "Receiver:\nOLSR" r"$\rightarrow$" "AP", '#ff7700')
        else:
            draw_brace_top(ax[0], (i, j), "Receiver:\nAP reconnect", '#ff7700')
    ax[0].set_xlabel("Time (seconds)")
    ax[0].set_ylabel("Signal AP (dBm)")
    ax_top = ax[0].twiny()
    ax[0].legend(loc='upper center')
    ax[0].grid()

    line0 = ax[1].plot(df_time_series['time'], df_time_series['packet_loss'], label='Packet loss')
    ax[1].set_xlabel("Time (seconds)")
    ax[1].set_ylabel("Packet loss")
    # ax[1].set_ylim(-5, 130)
    ax[1].yaxis.set_minor_locator(MultipleLocator(25))
    ax[1].set_ylim(-20, 600)
    ax[1].legend()
    ax[1].grid()

    line3 = ax[2].plot(df_time_series['time'], df_time_series['latency'], label='Latency')
    lat_max = ax[2].plot(df_time_series['time'], np.zeros(len(df_time_series['time'])) + df_summary.loc[0, 'max_latency_s'],
                         label='Max. latency', linestyle='dashed')
    lat_avg = ax[2].plot(df_time_series['time'], np.zeros(len(df_time_series['time'])) + df_summary.loc[0, 'avg_latency_s'],
                         label='Avg. latency', linestyle='dotted')
    ax[2].set_xlabel("Time (seconds)")
    ax[2].set_ylabel("End-to-end Latency (seconds)")
    ax[2].yaxis.set_minor_locator(MultipleLocator(0.1))
    ax[2].set_ylim(-0.1, 2.5)
    ax[2].legend()
    ax[2].grid()

    for x in ax:
        x.set_xlim(0, 175)
        x.xaxis.set_major_locator(MultipleLocator(10))
        x.xaxis.set_major_formatter(FormatStrFormatter('%d'))
        x.xaxis.set_minor_locator(MultipleLocator(2.0))
    ax_top.set_xlim(0, 175)
    ax_top.xaxis.set_major_locator(MultipleLocator(10))
    ax_top.xaxis.set_major_formatter(FormatStrFormatter('%d'))
    ax_top.xaxis.set_minor_locator(MultipleLocator(2.0))

    plt.tight_layout()
    if show:
        plt.show()
    else:
        plt.savefig(path + 'plot.pdf')


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
        resolution = int(xspan/xax_span*100)*2+1  # guaranteed uneven
        beta = 800./xax_span  # the higher this is, the smaller the radius

        x = np.linspace(xmin, xmax, resolution)
        x_half = x[:resolution//2+1]
        y_half_brace = (1/(1.+np.exp(-beta*(x_half-x_half[0])))
                        + 1/(1.+np.exp(-beta*(x_half-x_half[-1]))))
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
    parser.add_argument("-s", "--show", help="Show the plot instead of saving to file", action="store_true", default=False)
    parser.add_argument("-O", "--noolsr", help="No olsr when connection to AP is lost (default: False)", action='store_true', default=False)
    args = parser.parse_args()
    path = args.directory
    main(path, args.show, args.noolsr)
