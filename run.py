"""Run the taxi simulation for one or more fleet sizes.

Examples:
    # demand file as given (example: about half e-hailing), human-driven taxis only, 100 vehicles
    python run.py --fleet 100

    # all requests street-hailing, fleet sizes 100, 110, ..., 200
    python run.py --ehail-share 0 --fleet 100 200 10

    # all e-hailing, half ATs, idle ATs park on the road
    python run.py --ehail-share 1 --at-share 0.5 --at-idle 2 --fleet 150
"""

import argparse
import time

import pandas as pd

from taxisim import SimConfig, Network, Simulator
from taxisim.outputs import summary, save_run


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fleet", type=int, nargs="+", default=[100], metavar="M",
                    help="fleet size, or START STOP [STEP] for a range (STOP included)")
    ap.add_argument("--demand", default=SimConfig.demand_file, help="demand CSV")
    ap.add_argument("--ehail-share", type=float, default=None,
                    help="share p of e-hailing requests (default: matching_flag of the demand file)")
    ap.add_argument("--at-share", type=float, default=0.0, help="share r of autonomous taxis")
    ap.add_argument("--at-idle", type=int, default=1, choices=[1, 2, 3],
                    help="idle AT strategy: 1 random cruising, 2 park on road, 3 go to garage")
    ap.add_argument("--max-wait", type=int, default=3600, help="maximum waiting time (s)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=None, help="output folder (default: outputs/runs)")
    ap.add_argument("--no-detail", action="store_true", help="write the summary only")
    a = ap.parse_args()

    f = a.fleet
    sizes = f if len(f) == 1 else list(range(f[0], f[1] + 1, f[2] if len(f) > 2 else 1))
    cfg = SimConfig(demand_file=a.demand, ehail_share=a.ehail_share, at_share=a.at_share, at_idle=a.at_idle,
                    max_wait=a.max_wait, seed=a.seed, out_dir=a.out)
    net = Network(cfg)
    sim = Simulator(cfg, net)
    rows = []
    for m in sizes:
        t0 = time.time()
        req, fleet, state = sim.run(m, seed=cfg.seed * 100_000 + m)
        rows.append(summary(m, req, fleet))
        if not a.no_detail:
            save_run(cfg.out_dir, m, net, cfg.speed, req, fleet, state)
        s = rows[-1]
        print(f"m={m}: unmet {s['unmet']}, matching {s['matching_time']:.0f} s, "
              f"pickup {s['pickup_time']:.0f} s, ride {s['ride_time']:.0f} s  ({time.time() - t0:.0f} s)")
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(cfg.out_dir / "summary.csv", index=False)
    print(f"-> {cfg.out_dir}")


if __name__ == "__main__":
    main()
