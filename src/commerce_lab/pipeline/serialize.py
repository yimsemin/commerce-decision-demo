"""JSON-safe conversion of pandas/numpy values for the snapshot."""

from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd


def to_json_safe(value):
    if isinstance(value, dict):
        return {k: to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        f = float(value)
        return None if math.isnan(f) else f
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (pd.Timestamp, dt.date, dt.datetime)):
        return value.isoformat()
    return value


def records(df: pd.DataFrame) -> list[dict]:
    return [to_json_safe(r) for r in df.to_dict(orient="records")]
