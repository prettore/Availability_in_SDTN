from abc import ABC, abstractmethod
from typing import Tuple

import pandas as pd


class TraceReader(ABC):
    @classmethod
    @abstractmethod
    def get_trace(cls, trace_file: str) -> pd.DataFrame:
        pass


class TraceReaderMobilityPrediction(TraceReader):
    columns = {'time': float, 'x': float, 'y': float, 'state': int,
               'x_pred': float, 'y_pred': float, 'state_pred': float}

    @classmethod
    def read_trace(cls, trace_file: str) -> pd.DataFrame:
        df_trace_file = pd.read_csv(trace_file, dtype=cls.columns)
        return df_trace_file
