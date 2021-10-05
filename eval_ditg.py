import subprocess
import argparse
import numpy as np
import pandas as pd

from datetime import datetime


def main(data_path: str, start_time: float):
    subprocess.Popen(["ITGDec", "{}/sender.log".format(data_path), "-o", "{}/ditg-packets-send.csv".format(data_path)]).communicate()
    subprocess.Popen(["ITGDec", "{}/receiver.log".format(data_path), "-o", "{}/ditg-packets-recv.csv".format(data_path)]).communicate()
    print("\n\n")

    bitrate_window = 30

    ditg_packets_send = data_path + "/ditg-packets-send.csv"
    ditg_packets_recv = data_path + "/ditg-packets-recv.csv"
    packets_columns = ['packet_id', 'hour_tx', 'min_tx', 'sec_tx', 'hour_rx', 'min_rx', 'sec_rx', 'packet_length']
    df_packets_send = pd.read_csv(ditg_packets_send, sep=' ', header=None, names=packets_columns, skipinitialspace=True)
    df_packets_recv = pd.read_csv(ditg_packets_recv, sep=' ', header=None, names=packets_columns, skipinitialspace=True)

    df_packets_send = time_columns_to_timestamp(df_packets_send)
    df_packets_recv = time_columns_to_timestamp(df_packets_recv)
    print("*** Eval: Packets send: {}".format(len(df_packets_send['packet_id'])))
    # print(df_packets_send.head(10))
    print("*** Eval: Packets recv: {}".format(len(df_packets_recv['packet_id'])))
    # print(df_packets_recv.head(10))

    df_packets_merged = df_packets_send.merge(df_packets_recv, on='packet_id', how='left', suffixes=('_send', '_recv'))
    filter_merged_columns = ['packet_id', 'time_tx_send', 'time_rx_recv', 'packet_length_send']
    df_packets_merged = df_packets_merged[filter_merged_columns]
    print("*** Eval: Packets merged: {}".format(len(df_packets_merged['packet_id'])))
    # print(df_packets_merged.head(10))

    # create summary dataframe
    csv_columns_summary = ['total_time_s', 'packet_sent', 'packet_received', 'packet_dropped', 'packet_dropped_rate',
                           'min_latency_s', 'max_latency_s', 'avg_latency_s', 'sd_latency_s', 'avg_jitter_s',
                           'sd_jitter_s', 'avg_bitrate','sd_bitrate', 'avg_packetrate_pkts', 'round']
    df_summary = pd.DataFrame(columns=csv_columns_summary)

    # create time series dataframe
    #csv_columns_time_series = ['time', 'latency', 'jitter', 'packet_loss']
    csv_columns_time_series = ['time', 'bitrate', 'latency', 'jitter', 'packet_loss']
    df_time_series = pd.DataFrame(columns=csv_columns_time_series)

    print("*** Eval: Compute experiment duration")
    # experiment duration
    # df_summary.loc[0, 'total_time_s'] = np.nanmax(df_packets_merged['time_rx_recv']) - start_time
    df_summary.loc[0, 'total_time_s'] = np.nanmax(df_packets_merged['time_rx_recv']) - np.nanmin(df_packets_merged['time_tx_send'])
    # df_time_series['time'] = np.array(df_packets_merged['time_rx_recv']) - start_time
    df_time_series['time'] = np.array(df_packets_merged['time_rx_recv']) - start_time

    print("*** Eval: Compute bitrate")
    df_time_series['bitrate'] = pd.Series(
        computing_bit_rate(df_packets_merged, 'time_rx_recv', 'packet_length_send', bitrate_window))
    df_summary.loc[0, 'avg_bitrate'] = np.nanmean(df_time_series['bitrate'])
    df_summary.loc[0, 'sd_bitrate'] = np.nanstd(df_time_series['bitrate'])


    print("*** Eval: Compute latency")
    # end to end latency and latency summary
    df_time_series['latency'] = np.array(
        df_packets_merged['time_rx_recv'] - df_packets_merged['time_tx_send'])
    df_summary.loc[0, 'min_latency_s'] = np.nanmin(df_time_series['latency'])
    df_summary.loc[0, 'max_latency_s'] = np.nanmax(df_time_series['latency'])
    df_summary.loc[0, 'avg_latency_s'] = np.nanmean(df_time_series['latency'])
    df_summary.loc[0, 'sd_latency_s'] = np.nanstd(df_time_series['latency'])

    print("*** Eval: Compute packet summary")
    # Packets summary
    df_summary.loc[0, 'packet_sent'] = len(df_packets_merged['time_tx_send'].dropna())  # total packet sent
    df_summary.loc[0, 'packet_received'] = len(
        df_packets_merged['time_rx_recv'].dropna())  # total packet received
    df_summary.loc[0, 'packet_dropped'] = len(df_packets_merged['time_tx_send'].dropna()) - len(
        df_packets_merged['time_rx_recv'].dropna())  # total packet dropped
    df_summary.loc[0, 'packet_dropped_rate'] = df_summary.loc[0, 'packet_dropped'] * 100 / df_summary.loc[
        0, 'packet_sent']  # packet drop rate
    df_summary.loc[0, 'avg_packetrate_pkts'] = df_summary.loc[0, 'packet_received'] / df_summary.loc[
        0, 'total_time_s']  # packet rate

    print("*** Eval: Compute packet loss")
    # calculate packet loss
    df_time_series['packet_loss'] = df_time_series.apply(
        lambda row: 1 if np.isnan(row['time']) else 0, axis='columns')
    for row in range(1, len(df_time_series)):
        p0 = df_time_series.loc[row - 1, 'packet_loss']
        p1 = df_time_series.loc[row, 'packet_loss']
        if p1 != 0:
            df_time_series.loc[row, 'packet_loss'] = p0 + p1
        else:
            df_time_series.loc[row, 'packet_loss'] = 0

    print("*** Eval: Compute jitter")
    # calculate jitter
    df_tmp = df_time_series.dropna(subset=['time']).reset_index(drop=False)
    for row, _ in df_tmp.iterrows():
        if row == 0:
            df_tmp.loc[row, 'jitter'] = 0
        else:
            l0 = df_tmp.loc[row - 1, 'latency']
            l1 = df_tmp.loc[row, 'latency']
            df_tmp.loc[row, 'jitter'] = np.abs(l1 - l0)
    for row, _ in df_tmp.iterrows():
        index = df_tmp.loc[row, 'index']
        jitter = df_tmp.loc[row, 'jitter']
        df_time_series.loc[index, 'jitter'] = jitter
    df_summary.loc[0, 'avg_jitter_s'] = np.mean(df_time_series['jitter'])
    df_summary.loc[0, 'sd_jitter_s'] = np.nanstd(df_time_series['jitter'])

    print("*** Eval: Interpolate missing timestamps")
    # interpolate missed timestamp
    if np.isnan(df_time_series.loc[0, 'time']):
        df_time_series.loc[0, 'time'] = df_packets_merged.loc[0, 'time_tx_send'] + df_summary.loc[
            0, 'avg_latency_s']
    if np.isnan(df_time_series.loc[len(df_time_series) - 1, 'time']):
        df_time_series.loc[len(df_time_series) - 1, 'time'] = np.nanmax(df_time_series['time']) + df_summary.loc[
            0, 'avg_latency_s']
    df_time_series['time'] = df_time_series['time'].interpolate(method='linear', limit_direction='both', axis=0)

    print("*** Eval: Write summary and time series to files")
    df_summary.to_csv(data_path + 'summary.csv', index=False)
    df_time_series.to_csv(data_path + 'metrics_time_series.csv', index=False)

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

def time_columns_to_timestamp(df: pd.DataFrame, today: datetime = None):
    if not today:
        today = datetime.today()
    columns = ['packet_id', 'time_tx', 'time_rx', 'packet_length']
    df_new = pd.DataFrame(columns=columns)
    df_new['packet_id'] = df['packet_id']
    df_new['packet_length'] = df['packet_length']
    df_new['time_tx'] = df.apply(
        lambda r: today.replace(
            hour=2, minute=0, second=0, microsecond=0).timestamp() + (r['hour_tx'] * 3600 + r['min_tx'] * 60 + r['sec_tx']),
        axis='columns')
    df_new['time_rx'] = df.apply(
        lambda r: today.replace(
            hour=2, minute=0, second=0, microsecond=0).timestamp() + (r['hour_rx'] * 3600 + r['min_rx'] * 60 + r['sec_rx']),
        axis='columns')
    return df_new


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Tactical network experiment!")
    parser.add_argument("-d", "--directory", help="Directory of log files", type=str, required=True)
    parser.add_argument("-t", "--starttime",
                        help="Timestamp of the start of the experiment as synchronizing reference for measurements",
                        type=float, required=True)
    args = parser.parse_args()
    main(args.directory, args.starttime)
