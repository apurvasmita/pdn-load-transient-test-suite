"""
data_logger.py
--------------
CSV logging and per-rail statistical summary for PDN transient test results.

Output CSV columns
------------------
timestamp, rail_name, capture_index, dc_voltage_v, scope_vpp_mv,
vmax_v, vmin_v, deviation_pct, settling_time_us, ripple_mvpp,
pass_fail, fail_reasons
"""

import csv
import os
import logging
import numpy as np
from datetime import datetime
from typing import List, Dict

from .test_sequence import CaptureResult

logger = logging.getLogger(__name__)

CSV_FIELDS = [
    "timestamp", "rail_name", "capture_index",
    "dc_voltage_v", "scope_vpp_mv", "vmax_v", "vmin_v",
    "deviation_pct", "settling_time_us", "ripple_mvpp",
    "pass_fail", "fail_reasons",
]


class DataLogger:
    """
    Writes CaptureResult objects to a timestamped CSV file and
    computes per-rail statistics on demand.

    Usage
    -----
    dlog = DataLogger("results")
    dlog.log_result(result)          # stream one result
    dlog.log_results(result_list)    # bulk write
    stats = dlog.compute_statistics(result_list)
    """

    def __init__(self, output_dir: str = "results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        run_ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_path = os.path.join(output_dir, f"transient_test_{run_ts}.csv")
        self._init_csv()

    # ------------------------------------------------------------------ #
    #  CSV I/O                                                              #
    # ------------------------------------------------------------------ #

    def _init_csv(self):
        with open(self.csv_path, "w", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=CSV_FIELDS).writeheader()
        logger.info("CSV log opened: %s", self.csv_path)

    def log_result(self, r: CaptureResult):
        """Append one result row to the CSV (streaming, safe to call in a loop)."""
        settle_str = (
            f"{r.settling_time_us:.1f}"
            if r.settling_time_us != float("inf")
            else "INF"
        )
        row = {
            "timestamp":        r.timestamp,
            "rail_name":        r.rail_name,
            "capture_index":    r.capture_index,
            "dc_voltage_v":     f"{r.dc_voltage_v:.6f}",
            "scope_vpp_mv":     f"{r.scope_vpp_mv:.2f}",
            "vmax_v":           f"{r.vmax_v:.6f}",
            "vmin_v":           f"{r.vmin_v:.6f}",
            "deviation_pct":    f"{r.deviation_pct:.3f}",
            "settling_time_us": settle_str,
            "ripple_mvpp":      f"{r.ripple_mvpp:.2f}",
            "pass_fail":        r.pass_fail,
            "fail_reasons":     "; ".join(r.fail_reasons),
        }
        with open(self.csv_path, "a", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=CSV_FIELDS).writerow(row)

    def log_results(self, results: List[CaptureResult]):
        for r in results:
            self.log_result(r)
        logger.info("Logged %d results → %s", len(results), self.csv_path)

    # ------------------------------------------------------------------ #
    #  Statistics                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_statistics(results: List[CaptureResult]) -> Dict[str, dict]:
        """
        Compute per-rail summary statistics.

        Returns a dict keyed by rail name with the following fields:

        n_captures, n_pass, n_fail, pass_rate_pct,
        dc_mean_v, dc_std_v, dc_min_v, dc_max_v,
        ripple_mean_mvpp, ripple_max_mvpp,
        dev_mean_pct, dev_max_pct,
        settle_mean_us, settle_max_us, settle_inf_count
        """
        # Preserve insertion order of rails
        rail_names = list(dict.fromkeys(r.rail_name for r in results))
        stats: Dict[str, dict] = {}

        for rail in rail_names:
            sub = [r for r in results if r.rail_name == rail]
            n   = len(sub)
            if n == 0:
                continue

            n_pass = sum(1 for r in sub if r.pass_fail == "PASS")

            dc_vals     = np.array([r.dc_voltage_v     for r in sub])
            ripple_vals = np.array([r.ripple_mvpp       for r in sub])
            dev_vals    = np.array([r.deviation_pct     for r in sub])

            # Settling: replace inf with NaN so numpy ignores them
            settle_raw  = np.array([r.settling_time_us  for r in sub])
            settle_fin  = settle_raw[np.isfinite(settle_raw)]
            inf_count   = int(np.sum(~np.isfinite(settle_raw)))

            stats[rail] = {
                "n_captures":       n,
                "n_pass":           n_pass,
                "n_fail":           n - n_pass,
                "pass_rate_pct":    100.0 * n_pass / n,
                # DC voltage
                "dc_mean_v":        float(np.mean(dc_vals)),
                "dc_std_v":         float(np.std(dc_vals, ddof=1)) if n > 1 else 0.0,
                "dc_min_v":         float(np.min(dc_vals)),
                "dc_max_v":         float(np.max(dc_vals)),
                # Ripple
                "ripple_mean_mvpp": float(np.mean(ripple_vals)),
                "ripple_max_mvpp":  float(np.max(ripple_vals)),
                # Transient deviation
                "dev_mean_pct":     float(np.mean(dev_vals)),
                "dev_max_pct":      float(np.max(dev_vals)),
                # Settling time
                "settle_mean_us":   float(np.mean(settle_fin)) if len(settle_fin) else float("inf"),
                "settle_max_us":    float(np.max(settle_fin))  if len(settle_fin) else float("inf"),
                "settle_inf_count": inf_count,
            }

            logger.info(
                "[%s] %d/%d PASS | Vdc=%.4f±%.4f V | Ripple=%.1f mVpp "
                "| Dev=%.1f%% | Settle=%.0f µs",
                rail, n_pass, n,
                stats[rail]["dc_mean_v"], stats[rail]["dc_std_v"],
                stats[rail]["ripple_max_mvpp"],
                stats[rail]["dev_max_pct"],
                stats[rail]["settle_max_us"],
            )

        return stats
