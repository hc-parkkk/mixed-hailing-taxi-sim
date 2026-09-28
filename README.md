# mixed-hailing-taxi-sim

A network simulation of taxi services in which passengers request rides by **street-hailing** or **e-hailing**
and the fleet mixes **human-driven taxis (HTs)** and **autonomous taxis (ATs)**.
It accompanies the paper *Integrated analytical modeling of urban taxi services with mixed-hailing and a
heterogeneous fleet* (H. Park, J. Lee, H. Park, S. Kang).

## Installation

Python 3.10 or later.

```bash
pip install -r requirements.txt
```

## Usage

```bash
python run.py --fleet 100                                          # 100 HTs, demand file as given
python run.py --ehail-share 0 --fleet 100 200 10                   # street-hailing only, m = 100, 110, ..., 200
python run.py --ehail-share 1 --at-share 0.5 --at-idle 2 --fleet 150
```

| Option | Meaning | Default |
|---|---|---|
| `--fleet M` or `--fleet START STOP [STEP]` | Fleet size(s) | 100 |
| `--demand FILE` | Demand CSV | `data/demand/example_demand.csv` |
| `--ehail-share p` | Share of e-hailing requests; if omitted, `matching_flag` of the demand file is used | - |
| `--at-share r` | Share of ATs in the fleet | 0 |
| `--at-idle {1,2,3}` | What idle ATs do: 1 cruise randomly, 2 park on the road, 3 drive to the nearest garage | 1 |
| `--max-wait s` | Maximum waiting time before a request is unmet | 3600 |
| `--seed n` | Random seed | 1 |
| `--out DIR` | Output folder | `outputs/runs` |

From Python:

```python
from taxisim import SimConfig, Network, Simulator
cfg = SimConfig(ehail_share=0.5, at_share=0.5, at_idle=1)
requests, fleet, fleet_state = Simulator(cfg, Network(cfg)).run(fleet_size=150, seed=1)
```

All settings are listed in `taxisim/config.py`.

## How the simulation works

The simulation advances in 1-second steps. Requests arrive during a 2-hour service period, and the run continues
for the maximum waiting time afterwards so that late requests can still be served.

**Vehicles.** Each vehicle is idle, cruising empty, driving to an assigned passenger, or serving a passenger.
The first `round(m * r)` vehicles are ATs. Vehicles move on the shortest travel-time paths of the road network;
links can be driven in both directions.

**Matching.** Waiting requests are processed every second in the order they were made.

- *E-hailing*: every vacant (idle or cruising) HT or AT is a candidate if it can reach the passenger before
  10 minutes have passed since the request. The candidate with the shortest pickup time is dispatched.
- *Street-hailing*: only vacant HTs inside a box of +/-100 m around the passenger are candidates, which
  represents a driver who sees the passenger nearby. The nearest one is dispatched. ATs do not serve
  street-hailing.
- A request that is not matched within the maximum waiting time (60 minutes) is counted as unmet.

**Trips.** A dispatched vehicle drives to the passenger, picks them up, drives to the destination, and becomes
idle at the destination.

**Idle vehicles.** Idle HTs cruise to a randomly chosen node and pick a new random node on arrival.
Idle ATs follow the chosen strategy: cruise randomly like HTs, park where they are, or drive to the nearest
garage and park there. Parked ATs remain available for e-hailing.

**Outputs** (per fleet size m, in the output folder)

| File | Content |
|---|---|
| `summary.csv` | Unmet requests; mean matching, pickup and ride times of served requests; mean pickup, serving, empty-cruising and parking times per vehicle |
| `requests_m{m}.csv` | Each request: time, origin, destination, hailing type, status, vehicle, matching / pickup / ride times |
| `vehicles_m{m}.csv` | Each vehicle: AT or HT, accumulated pickup, serving, empty-cruising and parking times |
| `fleet_state_m{m}.csv` | Number of idle, assigned and serving vehicles every second |

Empty-cruising time is counted within the service period.

## Data

| Path | Content |
|---|---|
| `data/network/nodes.csv` | 1,301 nodes of the Daejeon road network: `node` id, `X` longitude, `Y` latitude |
| `data/network/links.csv` | 1,715 road links (3,076 directed records): `init_node`, `term_node`, `cost` travel time (s) |
| `data/demand/example_demand.csv` | Synthetic example: 565 requests uniformly distributed over the network and the 2-hour period |
| `data/initial_vehicles/vehicle_frame-{m}.csv` | Start nodes (column `origin`, row index of `nodes.csv`) for fleet sizes 30-400; start nodes are drawn at random for other sizes |

The trip data used in the paper were derived from the Taxi Operation Information Management System (TIMS) of Daejeon and
are not included. To use your own demand, provide a CSV with the columns

| Column | Meaning |
|---|---|
| `demand_timing` | Request time (s from the start of the service period) |
| `demand_loc`, `demand_des` | Origin and destination node ids (`node` in `nodes.csv`) |
| `matching_flag` | 1 e-hailing, 0 street-hailing (optional when `--ehail-share` is given) |

## License

MIT - see `LICENSE`.
