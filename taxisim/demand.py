"""Taxi requests."""

import numpy as np
import pandas as pd

from .config import SimConfig
from .network import Network

# request status
WAITING, ASSIGNED, COMPLETED, UNMET = 0, 1, 2, 3


class Requests:
    """Requests in first-come-first-served order and their outcomes.

    Input columns: demand_timing (request time, s), demand_loc and demand_des (origin and destination nodes),
    matching_flag (1 e-hailing, 0 street-hailing).
    """

    def __init__(self, df: pd.DataFrame):
        self.n = len(df)
        self.time = df["demand_timing"].to_numpy(np.int64)
        self.loc = df["demand_loc"].to_numpy(np.int64)
        self.des = df["demand_des"].to_numpy(np.int64)
        self.ehail = df["matching_flag"].to_numpy(np.int64)
        self.reset()

    def reset(self):
        n = self.n
        self.status = np.full(n, WAITING, dtype=np.int64)
        self.vehicle = np.zeros(n, dtype=np.int64)        # assigned vehicle (1-based), 0 = none
        self.matching_time = np.zeros(n, dtype=np.int64)  # request -> assignment
        self.pickup_time = np.zeros(n, dtype=np.int64)    # assignment -> boarding
        self.ride_time = np.zeros(n, dtype=np.int64)      # boarding -> alighting
        self.boarding = np.zeros(n, dtype=np.int64)       # boarding time
        self.alighting = np.zeros(n, dtype=np.int64)      # alighting time

    def to_frame(self, net: Network, speed: float) -> pd.DataFrame:
        return pd.DataFrame({
            "request_time": self.time,
            "origin": net.seq_to_orig[self.loc - 1],
            "destination": net.seq_to_orig[self.des - 1],
            "ehail": self.ehail,
            "status": np.array(["waiting", "assigned", "completed", "unmet"])[self.status],
            "vehicle": self.vehicle,
            "matching_time": self.matching_time,
            "pickup_time": self.pickup_time,
            "ride_time": self.ride_time,
            "boarding": self.boarding,
            "alighting": self.alighting,
            "ride_distance_m": self.ride_time / 3600 * speed * 1000,
        })


def load_requests(cfg: SimConfig, net: Network) -> Requests:
    df = pd.read_csv(cfg.path(cfg.demand_file), encoding="utf-8")
    df = df.sort_values("demand_timing", kind="stable").reset_index(drop=True)
    nodes = pd.concat([df["demand_loc"], df["demand_des"]])
    if nodes.isin(net.orig_to_seq.keys()).all():
        df["demand_loc"] = df["demand_loc"].map(net.orig_to_seq)
        df["demand_des"] = df["demand_des"].map(net.orig_to_seq)
    elif not nodes.between(1, net.n).all():
        raise ValueError("demand nodes are neither node ids of the node file nor indices 1..n")
    if cfg.ehail_share is not None:
        rng = np.random.default_rng(cfg.seed)
        df["matching_flag"] = (rng.random(len(df)) < cfg.ehail_share).astype(int)
    elif "matching_flag" not in df:
        raise ValueError("the demand file has no matching_flag column; set ehail_share")
    return Requests(df)
