import argparse

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as ani
from matplotlib.lines import Line2D

from matplotlib.ticker import MultipleLocator, FormatStrFormatter


class Animation(object):
    def __init__(self, duration, ax0, ax1, ax2, df_signal_send, df_signal_recv, df_time_series, send_disconnect, send_reconnect,
                 recv_disconnect, recv_reconnect):
        self.ax0 = ax0
        self.ax1 = ax1
        self.ax2 = ax2
        self.signal_send = df_signal_send
        self.signal_recv = df_signal_recv
        self.time_series = df_time_series
        self.send_disconnect = send_disconnect
        self.send_reconnect = send_reconnect
        self.recv_disconnect = recv_disconnect
        self.recv_reconnect = recv_reconnect

        # init signal plot
        self.line0_send = Line2D([], [], label='Signal strength sender', marker='v', color='tab:blue', linewidth=0)
        self.line0_send_avg = Line2D([], [], label='Signal strength sender moving avg.', marker=',', color='tab:blue')
        self.line0_recv = Line2D([], [], label='Signal strength receiver', marker='x', color='tab:orange', linewidth=0)
        self.line0_recv_avg = Line2D([], [], label='Signal strength receiver moving avg.', marker=',',
                                     color='tab:orange', linestyle='dashed')
        self.ax0.set_xlabel("Time (seconds)")
        self.ax0.set_ylabel("Signal AP (dBm)")
        self.ax0.set_ylim(-100, -30)
        self.ax0.set_xlim(0, duration)
        self.ax0.set_xticks([x for x in range(duration + 1)], True)
        self.ax00 = self.ax0.twiny()
        self.ax00.set_xlim(0, duration)
        self.ax00.set_xticks([x for x in range(duration + 1)], True)
        self.ax0.grid()
        self.ax0.add_line(self.line0_send)
        self.ax0.add_line(self.line0_send_avg)
        self.ax0.add_line(self.line0_recv)
        self.ax0.add_line(self.line0_recv_avg)
        self.ax0.legend(loc='upper center')

        # init spans for network handovers
        self.send_dspans = []
        for _ in send_disconnect:
            self.send_dspans.append(self.ax0.axvspan(-1, -1, ymin=0, ymax=0.5, color='#b8e1ff'))
        self.send_rspans = []
        for _ in send_reconnect:
            self.send_rspans.append(self.ax0.axvspan(-1, -1, ymin=0, ymax=0.5, color='#b8e1ff'))
        self.recv_dspans = []
        for _ in recv_disconnect:
            self.recv_dspans.append(self.ax0.axvspan(-1, -1, ymin=0.5, ymax=1, color='#ffcfa6'))
        self.recv_rspans = []
        for _ in recv_reconnect:
            self.recv_rspans.append(self.ax0.axvspan(-1, -1, ymin=0.5, ymax=1, color='#ffcfa6'))

        # init packet loss plot
        self.line1 = Line2D([], [], label='Packet loss')
        self.ax1.set_xlabel("Time (seconds)")
        self.ax1.set_ylabel("Packet loss")
        # self.ax1.yaxis.set_minor_locator(MultipleLocator(25))
        self.ax1.set_xlim(0, duration)
        self.ax1.set_xticks([x for x in range(duration + 1)], True)
        self.ax1.set_ylim(-5, 130)
        self.ax1.grid()
        self.ax1.add_line(self.line1)
        self.ax1.legend()

        # init latency plot
        self.line2 = Line2D([], [], label='Latency')
        self.ax2.set_xlabel("Time (seconds)")
        self.ax2.set_ylabel("End-to-end Latency (seconds)")
        # self.ax2.yaxis.set_minor_locator(MultipleLocator(0.1))
        self.ax2.set_xlim(0, duration)
        self.ax2.set_xticks([x for x in range(duration + 1)], True)
        self.ax2.set_ylim(-0.1, 2.5)
        self.ax2.grid()
        self.ax2.add_line(self.line2)
        self.ax2.legend()

    def __call__(self, i):
        if i == 0:
            self.line0_send.set_data([], [])
            self.line0_send_avg.set_data([], [])
            self.line0_recv.set_data([], [])
            self.line0_recv_avg.set_data([], [])
            self.line1.set_data([], [])
            self.line1.set_data([], [])
            lines = [self.line0_send, self.line0_send_avg, self.line0_recv, self.line0_recv_avg, self.line1, self.line2]
            spans = self.send_dspans + self.send_rspans + self.recv_dspans + self.recv_rspans
            return lines + spans
        signal_send = self.signal_send[self.signal_send['time'] <= i]
        signal_recv = self.signal_recv[self.signal_recv['time'] <= i]
        time_series = self.time_series[self.time_series['time'] <= i]
        self.line0_send.set_data(signal_send['time'], signal_send['signal'])
        self.line0_send_avg.set_data(signal_send['time'], signal_send['signal_avg'])
        self.line0_recv.set_data(signal_recv['time'], signal_recv['signal'])
        self.line0_recv_avg.set_data(signal_recv['time'], signal_recv['signal_avg'])
        self.line1.set_data(time_series['time'], time_series['packet_loss'])
        self.line2.set_data(time_series['time'], time_series['latency'])
        send_disconnect = [(n, m) for n, m in self.send_disconnect if n <= i]
        send_reconnect = [(n, m) for n, m in self.send_reconnect if n <= i]
        recv_disconnect = [(n, m) for n, m in self.recv_disconnect if n <= i]
        recv_reconnect = [(n, m) for n, m in self.recv_reconnect if n <= i]
        for k, v in enumerate(send_disconnect):
            n, m = v
            if m <= i:
                self.send_dspans[k].set_xy([[n, 0], [n, 0.5], [m, 0.5], [m, 0], [n, 0]])
            else:
                self.send_dspans[k].set_xy([[n, 0], [n, 0.5], [i, 0.5], [i, 0], [n, 0]])
        for k, v in enumerate(send_reconnect):
            n, m = v
            if m <= i:
                self.send_rspans[k].set_xy([[n, 0], [n, 0.5], [m, 0.5], [m, 0], [n, 0]])
            else:
                self.send_rspans[k].set_xy([[n, 0], [n, 0.5], [i, 0.5], [i, 0], [n, 0]])
        for k, v in enumerate(recv_disconnect):
            n, m = v
            if m <= i:
                self.recv_dspans[k].set_xy([[n, 0.5], [n, 1], [m, 1], [m, 0.5], [n, 0.5]])
            else:
                self.recv_dspans[k].set_xy([[n, 0.5], [n, 1], [i, 1], [i, 0.5], [n, 0.5]])
        for k, v in enumerate(recv_reconnect):
            n, m = v
            if m <= i:
                self.recv_rspans[k].set_xy([[n, 0.5], [n, 1], [m, 1], [m, 0.5], [n, 0.5]])
            else:
                self.recv_rspans[k].set_xy([[n, 0.5], [n, 1], [i, 1], [i, 0.5], [n, 0.5]])
        lines = [self.line0_send, self.line0_send_avg, self.line0_recv, self.line0_recv_avg, self.line1, self.line2]
        spans = self.send_dspans + self.send_rspans + self.recv_dspans + self.recv_rspans
        return lines + spans


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

    # initialize the plots for the visualization
    fig = plt.figure(figsize=(12, 8))
    ax0 = plt.subplot2grid((3, 1), (0, 0))
    ax1 = plt.subplot2grid((3, 1), (1, 0))
    ax2 = plt.subplot2grid((3, 1), (2, 0))

    duration = 175
    plot_animated = Animation(duration, ax0, ax1, ax2, df_signal_send, df_signal_recv, df_time_series, send_disconnect,
                              send_reconnect, recv_disconnect, recv_reconnect)
    frames = [t/10 for t in range(duration * 10)]
    animation = ani.FuncAnimation(fig, plot_animated, frames=frames, interval=50, blit=True)

    plt.tight_layout()
    if show:
        plt.show()
    else:
        animation.save(path + 'plot_animated.mp4')


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
