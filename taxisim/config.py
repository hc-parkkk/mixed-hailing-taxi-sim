"""Simulation settings."""

from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class SimConfig:
    # files (relative paths are resolved against `root`)
    root: Path = REPO_ROOT
    node_file: str = "data/network/nodes.csv"
    link_file: str = "data/network/links.csv"
    demand_file: str = "data/demand/example_demand.csv"
    vehicle_dir: str = "data/initial_vehicles"   # vehicle_frame-{m}.csv; random start nodes if missing
    out_dir: Path | None = None                  # default: <root>/outputs/runs

    # demand
    ehail_share: float | None = None     # None: e-hailing requests are given by the demand file (matching_flag);
                                         # otherwise each request is e-hailing with this probability
    service_period: int = 2 * 60 * 60    # requests arrive within this period (s)
    max_wait: int = 60 * 60              # a request not assigned within this time is unmet (s)

    # matching
    max_match: int = 10 * 60             # e-hailing: a vehicle is a candidate only if it can reach the
                                         # passenger before this time has passed since the request (s)
    catchment: float = 100.0             # street-hailing: half-width of the box around the passenger (m)

    # fleet
    at_share: float = 0.0                # share r of autonomous taxis (ATs)
    at_idle: int = 1                     # idle AT strategy: 1 random cruising, 2 park on road, 3 go to garage
    garages: tuple = (306189, 280765)    # garage node ids for at_idle = 3

    # output
    speed: float = 19.06                 # km/h, only used to report ride distance
    cruise_count_until: int | None = None  # empty cruising is counted up to this second
                                           # (default: end of the service period)
    seed: int = 1
    run_length: int | None = None        # simulated seconds (default: service_period + max_wait)

    x_half: float = field(init=False)    # catchment half-width in longitude arc seconds
    y_half: float = field(init=False)    # catchment half-width in latitude arc seconds

    def __post_init__(self):
        self.root = Path(self.root)
        if self.run_length is None:
            self.run_length = self.service_period + self.max_wait
        if self.cruise_count_until is None:
            self.cruise_count_until = self.service_period - 1
        # one arc second is about 24.7 m of longitude and 30.8 m of latitude at 36 deg N
        self.x_half = round(self.catchment / 24.7, 2)
        self.y_half = round(self.catchment / 30.8, 2)
        self.out_dir = Path(self.out_dir) if self.out_dir is not None else self.root / "outputs" / "runs"

    def path(self, rel) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else self.root / p
