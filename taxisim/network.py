"""Road network: shortest travel times and routes between all node pairs, and street-hailing catchments."""

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from .config import SimConfig


class Network:
    """Nodes are indexed 1..n in the order of the node file.

    Links can be driven in both directions; the travel time between two adjacent nodes is the smaller of the
    link costs given for the two directions. Travel times (s) and routes follow the shortest paths.
    """

    def __init__(self, cfg: SimConfig):
        node = pd.read_csv(cfg.path(cfg.node_file), encoding="utf-8")
        self.n = len(node)
        self.node_ids = np.arange(1, self.n + 1)
        self.orig_to_seq = dict(zip(node["node"], self.node_ids))
        self.seq_to_orig = node["node"].to_numpy()
        self.X = node["X"].to_numpy()      # longitude
        self.Y = node["Y"].to_numpy()      # latitude
        self._dms = {c: _to_dms(node[c].to_numpy()) for c in ("X", "Y")}

        link = pd.read_csv(cfg.path(cfg.link_file), encoding="utf-8")
        a = link["init_node"].map(self.orig_to_seq)
        b = link["term_node"].map(self.orig_to_seq)
        if a.isna().any() or b.isna().any():
            raise ValueError("link endpoints missing from the node file")
        w = np.zeros((self.n, self.n))
        w[a.to_numpy(int) - 1, b.to_numpy(int) - 1] = link["cost"].to_numpy(float)
        w = np.where(w > 0, w, np.inf)
        w = np.minimum(w, w.T)
        w[np.isinf(w)] = 0.0
        self.dist, self.pred = dijkstra(csr_matrix(w), directed=False, return_predecessors=True)
        if np.isinf(self.dist).any():
            print("[warn] the network is not connected")

        self.cfg = cfg
        self._box_cache: dict[int, np.ndarray] = {}

    def route(self, x: int, y: int) -> list[int]:
        """Shortest-path node sequence from x to y (both included); [x] when x == y."""
        if x == y:
            return [x]
        path = [y]
        p = self.pred[x - 1, y - 1]
        while p != -9999:
            path.append(p + 1)
            p = self.pred[x - 1, p]
        path.reverse()
        return path

    def box_nodes(self, loc: int) -> np.ndarray:
        """Nodes inside the street-hailing catchment box centred on node `loc`."""
        got = self._box_cache.get(loc)
        if got is None:
            xd, xm, xs = (v[loc - 1] for v in self._dms["X"])
            yd, ym, ys = (v[loc - 1] for v in self._dms["Y"])
            hx, hy = self.cfg.x_half, self.cfg.y_half
            x_hi, x_lo = xd + (xm + (xs + hx) / 60) / 60, xd + (xm + (xs - hx) / 60) / 60
            y_hi, y_lo = yd + (ym + (ys + hy) / 60) / 60, yd + (ym + (ys - hy) / 60) / 60
            got = self.node_ids[(self.X < x_hi) & (self.X >= x_lo) & (self.Y < y_hi) & (self.Y >= y_lo)]
            self._box_cache[loc] = got
        return got


def _to_dms(v: np.ndarray):
    """Degrees, minutes and seconds (rounded to 0.01 s) of decimal degrees."""
    d = np.floor(v)
    m = np.floor((v - d) * 60)
    s = np.round(((v - d) * 60 - m) * 60, 2)
    return d, m, s
