"""Run summaries and CSV output."""

import numpy as np
import pandas as pd

from .demand import Requests, WAITING, UNMET
from .fleet import Fleet
from .network import Network


def summary(fleet_size: int, req: Requests, fleet: Fleet) -> dict:
    """Unmet requests, mean times of served requests (s) and mean times per vehicle (s)."""
    served = req.vehicle > 0
    mean = (lambda x: float(x[served].mean())) if served.any() else (lambda x: float("nan"))
    return {
        "fleet": fleet_size,
        "unmet": int(np.count_nonzero((req.status == WAITING) | (req.status == UNMET))),
        "matching_time": mean(req.matching_time),
        "pickup_time": mean(req.pickup_time),
        "ride_time": mean(req.ride_time),
        "veh_pickup_time": float(fleet.pickup_time.mean()),
        "veh_serving_time": float(fleet.serving_time.mean()),
        "veh_cruising_time": float(fleet.cruising_time.mean()),
        "veh_parking_time": float(fleet.parking_time.mean()),
    }


def save_run(out_dir, fleet_size: int, net: Network, speed: float,
             req: Requests, fleet: Fleet, state: np.ndarray):
    """Write requests_m{m}.csv, vehicles_m{m}.csv and fleet_state_m{m}.csv."""
    out_dir.mkdir(parents=True, exist_ok=True)
    req.to_frame(net, speed).to_csv(out_dir / f"requests_m{fleet_size}.csv", index=False)
    fleet.to_frame().to_csv(out_dir / f"vehicles_m{fleet_size}.csv", index=False)
    pd.DataFrame(state, columns=["time", "idle", "assigned", "serving"]).to_csv(
        out_dir / f"fleet_state_m{fleet_size}.csv", index=False)
