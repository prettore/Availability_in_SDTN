import argparse
import pathlib
from typing import Tuple

import numpy as np
import pandas as pd


def main(args):
    columns = {'time': float, 'x': float, 'y': float, 'state': int,
               'x_pred': float, 'y_pred': float, 'state_pred': float}
    df_ref_node = pd.read_csv(args.refnodefile, dtype={'x': float, 'y': float})
    x_min, y_min = min(df_ref_node['x']), min(df_ref_node['y'])
    df_traces = dict()
    for file in args.file:
        df_trace = pd.read_csv(file, dtype=columns)
        df_trace = df_trace.drop([0]).reset_index(drop=True)
        df_traces.update({file: df_trace})
        x_min_new, _, y_min_new, _ = get_coord_min_max(df_trace)
        if x_min_new < x_min:
            x_min = x_min_new
        if y_min_new < y_min:
            y_min = y_min_new
    print(f"min(x) = {x_min}")
    print(f"min(y) = {y_min}")
    df_traces_NtoN = dict()
    for file, df_trace in df_traces.items():
        dtimes = []
        df_trace = df_trace.sort_values(by=['time'])
        start_time = df_trace.loc[0, 'time']
        for idx, row in df_trace.iterrows():
            df_trace.loc[idx, 'time'] = row['time'] - start_time
            if idx == 0:
                dtimes.append(0)
            else:
                dtime = df_trace.loc[idx, 'time'] - df_trace.loc[idx - 1, 'time']
                dtimes.append(dtime)
            df_trace.loc[idx, 'x'] = row['x'] - x_min + 100
            df_trace.loc[idx, 'y'] = row['y'] - y_min + 100
            df_trace.loc[idx, 'x_pred'] = row['x_pred'] - x_min + 100
            df_trace.loc[idx, 'y_pred'] = row['y_pred'] - y_min + 100
        df_trace['dtime'] = dtimes
        df_trace.to_csv(f"{file.name.rsplit('.', maxsplit=1)[0]}_pp.csv", index=False)
        df_trace_NtoN = df_trace.copy(deep=True)
        state_n2n = [5 for _ in range(len(df_trace))]
        df_trace_NtoN['state'] = state_n2n
        df_traces_NtoN.update({file: df_trace_NtoN})
        df_traces.update({file: df_trace})
        df_trace_NtoN.to_csv(f"{file.name.rsplit('.', maxsplit=1)[0]}_NtoN.csv", index=False)
    df_ref_node.loc[0, 'y'] = df_ref_node.loc[0, 'y'] - y_min + 100
    df_ref_node.loc[0, 'x'] = df_ref_node.loc[0, 'x'] - x_min + 100
    df_ref_node.to_csv(f"{args.refnodefile.rsplit('.', maxsplit=1)[0]}_pp.csv", index=False)
    for i, (file, df_trace) in enumerate(df_traces.items()):
        df_trace['node'] = i
    for i, (file, df_trace_NtoN) in enumerate(df_traces_NtoN.items()):
        df_trace_NtoN['node'] = i
    df_ref_node = pd.concat([df_ref_node, df_ref_node], ignore_index=True).reset_index(drop=True)
    df_ref_node['node'] = i + 1
    df_ref_node['state'] = "Base"
    df_ref_node['time'] = 0
    df_ref_node.loc[1, 'time'] = df_trace['time'].max()
    df_all = pd.concat([df for df in df_traces.values()] + [df_ref_node], ignore_index=True)
    df_all_NtoN = pd.concat([df for df in df_traces_NtoN.values()] + [df_ref_node], ignore_index=True)
    df_all.to_csv(f"{file.name.rsplit('.', maxsplit=1)[0]}_all-nodes.csv", index=False)
    df_all_NtoN.to_csv(f"{file.name.rsplit('.', maxsplit=1)[0]}_all-nodes_NtoN.csv", index=False)


def get_coord_min_max(df: pd.DataFrame) -> Tuple[float, float, float, float]:
    x_min = min(df['x'].min(), df['x_pred'].min())
    x_max = max(df['x'].max(), df['x_pred'].max())
    y_min = min(df['y'].min(), df['y_pred'].min())
    y_max = max(df['y'].max(), df['y_pred'].max())
    return x_min, x_max, y_min, y_max


def parse_args():
    parser = argparse.ArgumentParser(description="Preprocesses trace files that have the output format of the CAMS"
                                                 " mobility prediction (can be found in the CAMS output in the"
                                                 " 'test_results' directory ending on '*pred_trace.csv'.\nInput can be"
                                                 " multiple Trace files (one for each node) in case a convoy should be"
                                                 " simulated.\nOutput are the trace files needed for the mobility"
                                                 " prediction handover ('*_pp.csv' and '*_NtoN.csv') as well as"
                                                 " according trace files for the RSSI handover ('*_all-nodes.csv' and"
                                                 " '*_all-nodes_NtoN.csv' such that both mechanisms can be compared"
                                                 " using the same scenario.")
    parser.add_argument("-r", "--refnodefile", type=str, required=True,
                        help="Simple csv file with two columns x, y and one row containing the position of the"
                             " reference node (or base station)")
    parser.add_argument("file", type=argparse.FileType('r'), nargs='+',
                        help="Trace files in the output format of the CAMS mobility prediction. Multiple files can be"
                             " provided (one for each node) in case a convoy should be simulated.")
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = parse_args()
    main(args)
