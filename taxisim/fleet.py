"""Taxi fleet."""

import numpy as np
import pandas as pd

from .config import SimConfig

# vehicle state
IDLE, ASSIGNED, SERVING, CRUISING = 0, 1, 2, 3
#   IDLE      standing at `origin` (choosing a cruising target, or parked)
#   ASSIGNED  driving to the passenger
#   SERVING   passenger on board
#   CRUISING  driving empty towards `target`


class Fleet:
    """Vehicles 0..n-1; the first round(n * at_share) vehicles are ATs."""

    def __init__(self, origin: np.ndarray, cfg: SimConfig):
        n = self.n = len(origin)
        self.origin = origin.astype(np.int64).copy()   # current node while idle or cruising
        self.pickup = np.zeros(n, dtype=np.int64)      # passenger origin while assigned or serving
        self.dropoff = np.zeros(n, dtype=np.int64)     # passenger destination while assigned or serving
        self.location = np.zeros(n, dtype=np.int64)    # last node passed on a passenger trip
        self.state = np.full(n, IDLE, dtype=np.int64)
        self.target = np.zeros(n, dtype=np.int64)      # cruising target node
        self.next_node = np.zeros(n, dtype=np.int64)   # next node on the cruising route
        self.next_time = np.zeros(n, dtype=np.int64)   # arrival time at next_node
        self.is_at = np.zeros(n, dtype=np.int64)
        self.is_at[:round(n * cfg.at_share)] = 1
        # accumulated time (s)
        self.pickup_time = np.zeros(n, dtype=np.int64)
        self.serving_time = np.zeros(n, dtype=np.int64)
        self.cruising_time = np.zeros(n, dtype=np.int64)
        self.parking_time = np.zeros(n, dtype=np.int64)

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame({
            "vehicle": np.arange(1, self.n + 1), "is_at": self.is_at,
            "pickup_time": self.pickup_time, "serving_time": self.serving_time,
            "cruising_time": self.cruising_time, "parking_time": self.parking_time,
        })


def load_fleet(cfg: SimConfig, n_nodes: int, fleet_size: int, rng) -> Fleet:
    """Start nodes from vehicle_frame-{m}.csv (column `origin`, node indices 1..n), else uniformly random."""
    f = cfg.path(cfg.vehicle_dir) / f"vehicle_frame-{fleet_size}.csv"
    if f.exists():
        origin = pd.read_csv(f)["origin"].to_numpy()
    else:
        origin = rng.integers(1, n_nodes + 1, size=fleet_size)
    return Fleet(origin, cfg)
