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
        state_n2n = [5 for _ in range(len(df_trace))]
        df_trace['state'] = state_n2n
        df_trace.to_csv(f"{file.name.rsplit('.', maxsplit=1)[0]}_NtoN.csv", index=False)
    df_ref_node.loc[0, 'x'] = df_ref_node.loc[0, 'x'] - x_min + 100
    df_ref_node.loc[0, 'y'] = df_ref_node.loc[0, 'y'] - y_min + 100
    df_ref_node.to_csv(f"{args.refnodefile.rsplit('.', maxsplit=1)[0]}_pp.csv", index=False)


def get_coord_min_max(df: pd.DataFrame) -> Tuple[float, float, float, float]:
    x_min = min(df['x'].min(), df['x_pred'].min())
    x_max = max(df['x'].max(), df['x_pred'].max())
    y_min = min(df['y'].min(), df['y_pred'].min())
    y_max = max(df['y'].max(), df['y_pred'].max())
    return x_min, x_max, y_min, y_max


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--refnodefile", type=str, required=True)
    parser.add_argument("file", type=argparse.FileType('r'), nargs='+')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = parse_args()
    main(args)
