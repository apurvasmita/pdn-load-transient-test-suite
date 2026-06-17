#!/usr/bin/env python3
"""
main.py
=======
Entry point for the Digantara PDN Load Transient Test Suite.

Usage
-----
# Real hardware run:
python main.py --config config/test_config.yaml --operator "A. Sharma" --dut-sn SN-001

# Dry-run (synthetic data, no instruments required):
python main.py --dry-run --dut-sn SN-DRY

# Enable verbose SCPI logging:
python main.py --dry-run --log-level DEBUG

Command-line arguments
----------------------
--config      Path to YAML config file   [default: config/test_config.yaml]
--operator    Operator name for the report
--dut-sn      Board serial number
--board-rev   PCB revision string
--output-dir  Directory for CSV and HTML output [default: results]
--log-level   Python logging level [default: INFO]
--dry-run     Simulate with synthetic data; no real instruments needed
--no-interact Suppress operator prompts between rails
"""

import sys
import os
import logging
import argparse
import random
import time
import yaml
from datetime import datetime

from src.instruments import (
    Keithley2230,
    Keithley2380,
    KeysightDSOX6004A,
    KeithelyDMM6500,
)
from src.test_sequence import (
    LoadTransientTestSequence,
    RailConfig,
    CaptureResult,
    MAX_RIPPLE_MVPP,
    MAX_DEVIATION_PCT,
    MAX_SETTLING_US,
    CAPTURES_PER_RAIL,
)
from src.data_logger      import DataLogger
from src.report_generator import ReportGenerator


# ────────────────────────────────────────────────────────────────────────────
def setup_logging(level: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, f"run_{datetime.now():%Y%m%d_%H%M%S}.log")
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )
    return log_path


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_rail_configs(cfg: dict) -> list[RailConfig]:
    return [
        RailConfig(
            name            = r["name"],
            nominal_v       = r["nominal_voltage"],
            tolerance_pct   = r["tolerance_pct"],
            max_current_a   = r["max_current"],
            scope_channel   = r["scope_channel"],
            low_load_pct    = r.get("low_current_pct",  10.0),
            high_load_pct   = r.get("high_current_pct", 90.0),
        )
        for r in cfg["rails"]
    ]


# ────────────────────────────────────────────────────────────────────────────
#  Hardware path                                                              #
# ────────────────────────────────────────────────────────────────────────────

def run_hardware(args, cfg, rails, dlog, reporter, metadata, logger):
    inst_cfg = cfg["instruments"]
    psu   = Keithley2230(inst_cfg["power_supply"]["resource"])
    eload = Keithley2380(inst_cfg["electronic_load"]["resource"])
    scope = KeysightDSOX6004A(inst_cfg["oscilloscope"]["resource"])
    dmm   = KeithelyDMM6500(inst_cfg["dmm"]["resource"])

    try:
        logger.info("Connecting to instruments …")
        psu.connect();   eload.connect()
        scope.connect(); dmm.connect()
        scope.reset()

        # --- Configure PSU input channel ---
        ic = cfg["input_supply"]
        psu.configure(
            channel       = ic["channel"],
            voltage       = ic["voltage"],
            current_limit = ic["current_limit"],
        )

        # --- Run sequence ---
        seq     = LoadTransientTestSequence(psu, eload, scope, dmm, rails)
        results = seq.run_all(interactive=not args.no_interact)

        _finalise(results, dlog, reporter, metadata, logger)

    finally:
        try:
            eload.disable_input()
            psu.disable_output()
        except Exception:
            pass
        for inst in (psu, eload, scope, dmm):
            try:
                inst.close()
            except Exception:
                pass


# ────────────────────────────────────────────────────────────────────────────
#  Dry-run path (synthetic data)                                              #
# ────────────────────────────────────────────────────────────────────────────

def run_dry(rails, dlog, reporter, metadata, logger):
    """
    Generate plausible synthetic CaptureResult objects for development,
    CI, and offline report validation.  Three out of ten captures on the
    +3V3 rail are biased to fail (mimics Board SN-017 scenario from Q2b).
    """
    logger.warning("DRY-RUN MODE — synthetic data, no instruments required")
    rng     = random.Random(42)
    results: list[CaptureResult] = []

    for rail in rails:
        for n in range(1, CAPTURES_PER_RAIL + 1):
            # Inject three failures on +3V3, as described in Q2b
            inject_fail = (rail.name == "+3V3" and n in (3, 7, 9))

            dc_v       = rail.nominal_v + rng.gauss(0.005, 0.004)
            ripple     = rng.gauss(28.0, 6.0) + (35.0 if inject_fail else 0.0)
            dev        = abs(rng.gauss(1.8, 0.6))  + (4.2 if inject_fail else 0.0)
            settle     = abs(rng.gauss(180.0, 45.0)) + (380.0 if inject_fail else 0.0)

            fail_reasons = []
            if ripple  > MAX_RIPPLE_MVPP:   fail_reasons.append(f"Ripple {ripple:.1f} mVpp > {MAX_RIPPLE_MVPP:.0f} mVpp")
            if dev     > MAX_DEVIATION_PCT: fail_reasons.append(f"Deviation {dev:.1f} % > {MAX_DEVIATION_PCT:.0f} %")
            if settle  > MAX_SETTLING_US:   fail_reasons.append(f"Settling {settle:.0f} µs > {MAX_SETTLING_US:.0f} µs")

            results.append(CaptureResult(
                rail_name        = rail.name,
                capture_index    = n,
                timestamp        = datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
                dc_voltage_v     = dc_v,
                scope_vpp_mv     = ripple * 1.1,
                vmax_v           = dc_v + ripple / 1000,
                vmin_v           = dc_v - ripple / 1000,
                deviation_pct    = dev,
                settling_time_us = settle,
                ripple_mvpp      = ripple,
                pass_fail        = "FAIL" if fail_reasons else "PASS",
                fail_reasons     = fail_reasons,
            ))
            time.sleep(0.01)   # simulate capture cadence

    _finalise(results, dlog, reporter, metadata, logger)


# ────────────────────────────────────────────────────────────────────────────
#  Common post-test actions                                                   #
# ────────────────────────────────────────────────────────────────────────────

def _finalise(results, dlog, reporter, metadata, logger):
    dlog.log_results(results)
    stats = DataLogger.compute_statistics(results)

    report_path = reporter.generate(results, stats, metadata)

    n_pass = sum(1 for r in results if r.pass_fail == "PASS")
    n_tot  = len(results)
    logger.info("─" * 60)
    logger.info("TOTAL: %d / %d captures PASS", n_pass, n_tot)
    logger.info("CSV  : %s", dlog.csv_path)
    logger.info("HTML : %s", report_path)


# ────────────────────────────────────────────────────────────────────────────
#  CLI                                                                        #
# ────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Digantara PDN Load Transient Test Suite",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--config",      default="config/test_config.yaml",
                   help="YAML configuration file")
    p.add_argument("--operator",    default="Test Engineer",
                   help="Operator name (appears in report header)")
    p.add_argument("--dut-sn",      default="SN-XXX",
                   help="DUT board serial number")
    p.add_argument("--board-rev",   default="Rev-A",
                   help="PCB revision")
    p.add_argument("--output-dir",  default="results",
                   help="Output directory for CSV, HTML, and log")
    p.add_argument("--log-level",   default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                   help="Python logging verbosity level")
    p.add_argument("--dry-run",     action="store_true",
                   help="Run with synthetic data (no instruments required)")
    p.add_argument("--no-interact", action="store_true",
                   help="Suppress between-rail operator prompts")
    return p.parse_args()


def main():
    args   = parse_args()
    log_fp = setup_logging(args.log_level, args.output_dir)
    logger = logging.getLogger("main")
    logger.info("PDN Transient Test Suite starting")
    logger.info("Log file: %s", log_fp)

    cfg   = load_config(args.config)
    rails = build_rail_configs(cfg)

    metadata = {
        "operator":  args.operator,
        "dut_sn":    args.dut_sn + (" [DRY RUN]" if args.dry_run else ""),
        "board_rev": args.board_rev,
    }

    dlog     = DataLogger(output_dir=args.output_dir)
    reporter = ReportGenerator(output_dir=args.output_dir)

    if args.dry_run:
        run_dry(rails, dlog, reporter, metadata, logger)
    else:
        run_hardware(args, cfg, rails, dlog, reporter, metadata, logger)


if __name__ == "__main__":
    main()
