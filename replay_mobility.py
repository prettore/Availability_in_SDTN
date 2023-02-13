import os
import csv
import pandas as pd

from threading import Thread
from time import sleep

from mn_wifi.node import Node_wifi


class CustomMobilityReplayer:
    columns = ["time", "x", "y", "state", "x_pred", "y_pred", "state_pred", "dtime"]

    def __init__(self, node_a: Node_wifi, node_b: Node_wifi, trace_a: pd.DataFrame, trace_b: pd.DataFrame,
                 statistics_dir: str, time_factor: float = 1.0):
        self.file_a = f"{statistics_dir}/{node_a.name}_position_state.csv"
        self.file_b = f"{statistics_dir}/{node_b.name}_position_state.csv"
        self.time_factor = time_factor
        self.thread = Thread(name="replaying_mobility", target=self.replay, args=(node_a, node_b, trace_a, trace_b))
        self.thread.daemon = True
        self.thread._keep_alive = True

    def start_replaying(self):
        self.thread.start()

    def replay(self, node_a: Node_wifi, node_b: Node_wifi, trace_a: pd.DataFrame, trace_b: pd.DataFrame):
        for row_a, row_b in zip(trace_a.iterrows(), trace_b.iterrows()):
            i, row_a = row_a
            j, row_b = row_b
            sleep(row_a['dtime'] * (1/self.time_factor))
            node_a.setPosition(f"{row_a['x']},{row_a['y']},0")
            node_b.setPosition(f"{row_b['x']},{row_b['y']},0")
            self.write_or_append_csv_to_file(dict(row_a.to_dict()), self.columns, self.file_a)
            self.write_or_append_csv_to_file(dict(row_b.to_dict()), self.columns, self.file_b)
            # row_a.to_frame().T.to_csv(self.file_a, index=False)
            # row_b.to_frame().T.to_csv(self.file_b, index=False)

    def write_or_append_csv_to_file(self, data: dict, csv_columns: list, file: str):
        if os.path.isfile(file):
            with open(file, 'a') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
                writer.writerow(data)
        else:
            with open(file, 'w') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
                writer.writeheader()
                writer.writerow(data)
