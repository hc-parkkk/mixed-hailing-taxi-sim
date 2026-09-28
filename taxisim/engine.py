"""Time-driven simulation with a 1-second step.

Each second:
  1. match waiting requests in first-come-first-served order (requests waiting longer than max_wait become unmet);
  2. move vehicles on passenger trips to the node they reach at this second;
  3. board and drop off passengers;
  4. move idle vehicles (HTs cruise randomly; ATs cruise, park, or head to a garage);
  5. record the number of idle, assigned and serving vehicles.
"""

import math

import numpy as np

from .config import SimConfig
from .demand import Requests, load_requests, WAITING, ASSIGNED, COMPLETED, UNMET
from .fleet import Fleet, load_fleet, IDLE, ASSIGNED as V_ASSIGNED, SERVING, CRUISING
from .network import Network


class Simulator:
    def __init__(self, cfg: SimConfig, net: Network, requests: Requests | None = None):
        self.cfg = cfg
        self.net = net
        self.req = requests if requests is not None else load_requests(cfg, net)
        self.garages = np.array([net.orig_to_seq[g] for g in cfg.garages], dtype=np.int64)

    def run(self, fleet_size: int, seed: int | None = None):
        """Simulate one day with `fleet_size` vehicles. Returns (requests, fleet, fleet_state)."""
        cfg = self.cfg
        self.rng = np.random.default_rng(cfg.seed if seed is None else seed)
        self.req.reset()
        self.fleet = load_fleet(cfg, self.net.n, fleet_size, self.rng)
        self.trip_nodes: dict[int, list[tuple[int, int]]] = {}   # second -> [(vehicle, node reached)]
        state = np.zeros((cfg.run_length, 4), dtype=np.int64)   # time, idle, assigned, serving

        for sec in range(1, cfg.run_length + 1):
            self._match(sec)
            self._advance_trips(sec)
            self._board_and_alight(sec)
            self._move_idle(sec)
            s = self.fleet.state
            state[sec - 1] = (sec, np.count_nonzero((s == IDLE) | (s == CRUISING)),
                              np.count_nonzero(s == V_ASSIGNED), np.count_nonzero(s == SERVING))
        return self.req, self.fleet, state

    # ------------------------------------------------------------------ matching

    def _match(self, sec: int):
        cfg, net, q, F = self.cfg, self.net, self.req, self.fleet
        for i in np.where((q.status == WAITING) & (q.time <= sec))[0]:
            waited = sec - int(q.time[i])
            if waited > cfg.max_wait:
                q.status[i] = UNMET
                continue
            loc = int(q.loc[i])
            vacant = np.where((F.state == IDLE) | (F.state == CRUISING))[0]
            if q.ehail[i] == 1:
                # e-hailing: any vacant HT or AT that can reach the passenger within the matching window
                cand = vacant[net.dist[F.origin[vacant] - 1, loc - 1] < cfg.max_match - waited]
            else:
                # street-hailing: vacant HTs inside the catchment box around the passenger
                cand = vacant[(F.is_at[vacant] == 0) & np.isin(F.origin[vacant], net.box_nodes(loc))]
            if cand.size == 0:
                continue
            # dispatch the candidate with the shortest pickup time (lowest vehicle number on ties)
            self._assign(sec, i, int(cand[np.argmin(net.dist[F.origin[cand] - 1, loc - 1])]))

    def _assign(self, sec: int, i: int, veh: int):
        net, q, F = self.net, self.req, self.fleet
        loc, des = int(q.loc[i]), int(q.des[i])
        start = int(F.origin[veh])
        F.pickup[veh], F.dropoff[veh], F.state[veh] = loc, des, V_ASSIGNED
        F.location[veh] = start
        F.target[veh] = F.next_node[veh] = F.next_time[veh] = 0

        pickup = round(float(net.dist[start - 1, loc - 1]))
        ride = round(float(net.dist[loc - 1, des - 1]))
        q.status[i] = ASSIGNED
        q.vehicle[i] = veh + 1
        q.matching_time[i] = sec - int(q.time[i])
        q.pickup_time[i] = pickup
        q.ride_time[i] = ride
        q.boarding[i] = sec + pickup
        q.alighting[i] = sec + pickup + ride
        self._schedule_trip(veh, net.route(start, loc) + net.route(loc, des), sec)

    def _schedule_trip(self, veh: int, nodes: list[int], sec: int):
        """Times at which the vehicle reaches each node of its trip (link times rounded to seconds)."""
        t = sec
        entries = [(nodes[0], t)]
        for a, b in zip(nodes[:-1], nodes[1:]):
            t += round(float(self.net.dist[a - 1, b - 1]))
            entries.append((b, t))
        for node, tt in entries:
            if tt < self.cfg.run_length or tt == sec:
                self.trip_nodes.setdefault(tt, []).append((veh, node))

    def _advance_trips(self, sec: int):
        for veh, node in self.trip_nodes.pop(sec, ()):
            self.fleet.location[veh] = node

    # ------------------------------------------------------------------ boarding and alighting

    def _board_and_alight(self, sec: int):
        q, F = self.req, self.fleet
        for v1 in q.vehicle[(q.boarding == sec) & (q.status == ASSIGNED)]:
            if F.state[v1 - 1] == V_ASSIGNED:
                F.state[v1 - 1] = SERVING
        done = (q.alighting == sec) & (q.status == ASSIGNED)
        q.status[done] = COMPLETED
        for v1 in q.vehicle[q.alighting == sec]:
            v = v1 - 1
            if F.state[v] == SERVING:
                F.origin[v] = F.location[v]
                F.pickup[v] = F.dropoff[v] = F.location[v] = 0
                F.state[v] = IDLE

    # ------------------------------------------------------------------ idle vehicles

    def _move_idle(self, sec: int):
        cfg, F = self.cfg, self.fleet
        state = F.state.copy()   # each vehicle acts on its state at the start of this stage
        F.pickup_time[state == V_ASSIGNED] += 1
        F.serving_time[state == SERVING] += 1
        for v in np.where((state == IDLE) | (state == CRUISING))[0]:
            v = int(v)
            if state[v] == CRUISING:
                self._cruise(v, sec)
            elif F.is_at[v] == 0 or cfg.at_idle == 1:
                self._start_cruise(v, sec, int(self.rng.integers(1, self.net.n + 1)))
            elif cfg.at_idle == 2:
                F.parking_time[v] += 1
            elif F.origin[v] in self.garages:
                F.parking_time[v] += 1
            else:
                g = self.garages[int(np.argmin(self.net.dist[F.origin[v] - 1, self.garages - 1]))]
                self._start_cruise(v, sec, int(g))

    def _start_cruise(self, v: int, sec: int, target: int):
        F = self.fleet
        self._count_cruise(v, sec)
        F.location[v] = F.origin[v]
        F.state[v] = CRUISING
        F.target[v] = target
        self._head_to_target(v, sec)

    def _cruise(self, v: int, sec: int):
        F = self.fleet
        self._count_cruise(v, sec)
        if F.next_time[v] == sec:
            F.origin[v] = F.next_node[v]
            F.next_node[v] = F.next_time[v] = 0
            self._head_to_target(v, sec)

    def _head_to_target(self, v: int, sec: int):
        """Set the next node towards the target, or become idle on arrival."""
        F, net = self.fleet, self.net
        if F.origin[v] != F.target[v]:
            route = net.route(int(F.origin[v]), int(F.target[v]))
            F.next_node[v] = route[1]
            F.next_time[v] = sec + math.ceil(net.dist[route[0] - 1, route[1] - 1])
        else:
            F.target[v] = 0
            F.state[v] = IDLE

    def _count_cruise(self, v: int, sec: int):
        if sec <= self.cfg.cruise_count_until:
            self.fleet.cruising_time[v] += 1
