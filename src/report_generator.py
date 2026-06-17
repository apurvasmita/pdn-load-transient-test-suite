"""
report_generator.py
-------------------
Generates a self-contained HTML test report from CaptureResult objects
and the statistics dict produced by DataLogger.compute_statistics().

The HTML file embeds all data inline (no external dependencies) so it
can be archived alongside the CSV and opened on any machine.
"""

import os
import logging
from datetime import datetime
from typing import List, Dict

from .test_sequence import (
    CaptureResult,
    MAX_RIPPLE_MVPP,
    MAX_DEVIATION_PCT,
    MAX_SETTLING_US,
    SETTLING_BAND_PCT,
    CAPTURES_PER_RAIL,
    TRANSIENT_FREQ_HZ,
)

logger = logging.getLogger(__name__)

# ── colour palette ──────────────────────────────────────────────────────────
PASS_GREEN = "#27ae60"
FAIL_RED   = "#e74c3c"
HDR_DARK   = "#2c3e50"
HDR_MID    = "#34495e"
ALT_ROW    = "#f4f6f7"

CSS = f"""
  body  {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 28px;
           color: #222; background: #fff; }}
  h1   {{ color: {HDR_DARK}; margin-bottom: 4px; }}
  h2   {{ color: {HDR_MID}; border-bottom: 2px solid #bdc3c7;
           padding-bottom: 4px; margin-top: 28px; }}
  .badge {{ display: inline-block; padding: 6px 20px; border-radius: 5px;
            color: #fff; font-size: 1.1em; font-weight: bold; }}
  .pass-badge {{ background: {PASS_GREEN}; }}
  .fail-badge {{ background: {FAIL_RED}; }}
  .meta  {{ background: {ALT_ROW}; border: 1px solid #d5d8dc;
            padding: 12px 16px; border-radius: 5px; margin-bottom: 18px;
            line-height: 1.7; }}
  table  {{ border-collapse: collapse; width: 100%; margin-bottom: 24px;
            font-size: 0.92em; }}
  th     {{ background: {HDR_DARK}; color: #fff; padding: 8px 10px;
            text-align: left; white-space: nowrap; }}
  td     {{ border: 1px solid #d5d8dc; padding: 6px 9px;
            vertical-align: top; }}
  tr:nth-child(even) td {{ background: {ALT_ROW}; }}
  .pass  {{ color: {PASS_GREEN}; font-weight: bold; }}
  .fail  {{ color: {FAIL_RED};   font-weight: bold; }}
  .mono  {{ font-family: monospace; font-size: 0.88em; }}
  footer {{ margin-top: 40px; font-size: 0.8em; color: #888; }}
"""


class ReportGenerator:
    """
    Generates an HTML test report.

    Usage
    -----
    rg = ReportGenerator("results")
    path = rg.generate(results, stats, metadata)
    """

    def __init__(self, output_dir: str = "results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    # ------------------------------------------------------------------ #
    #  Public API                                                           #
    # ------------------------------------------------------------------ #

    def generate(self,
                 results: List[CaptureResult],
                 stats:   Dict[str, dict],
                 metadata: Dict | None = None) -> str:
        """
        Write report to a timestamped HTML file and return the path.

        Parameters
        ----------
        results  : flat list of all CaptureResult objects
        stats    : output of DataLogger.compute_statistics(results)
        metadata : optional dict with keys: operator, dut_sn, board_rev, etc.
        """
        meta  = metadata or {}
        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        path  = os.path.join(self.output_dir, f"pdn_transient_report_{ts}.html")

        overall_pass = all(r.pass_fail == "PASS" for r in results)

        html = "\n".join([
            "<!DOCTYPE html>",
            '<html lang="en"><head>',
            '<meta charset="UTF-8">',
            "<title>PDN Load Transient Test Report — Digantara</title>",
            f"<style>{CSS}</style>",
            "</head><body>",
            self._header_section(meta, overall_pass),
            self._assumptions_section(),
            self._summary_section(stats),
            self._criteria_section(),
            self._detail_section(results),
            self._footer_section(),
            "</body></html>",
        ])

        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)

        logger.info("HTML report saved: %s", path)
        return path

    # ------------------------------------------------------------------ #
    #  Section builders                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _header_section(meta: dict, overall_pass: bool) -> str:
        badge_cls = "pass-badge" if overall_pass else "fail-badge"
        badge_txt = "OVERALL PASS" if overall_pass else "OVERALL FAIL"
        return f"""
<h1>PDN Load Transient Test Report</h1>
<div class="meta">
  <b>Date/Time :</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp;
  <b>Operator  :</b> {meta.get('operator',  'N/A')} &nbsp;|&nbsp;
  <b>DUT S/N   :</b> {meta.get('dut_sn',   'N/A')} &nbsp;|&nbsp;
  <b>Board Rev :</b> {meta.get('board_rev', 'N/A')}<br>
  <b>Instrument setup:</b>
  Keithley 2230-30-1 (PSU) · Keithley 2380 (E-Load) ·
  Keysight DSOX6004A (Scope) · Keithley DMM6500 (DMM)<br>
  <b>Result: </b><span class="badge {badge_cls}">{badge_txt}</span>
</div>"""

    @staticmethod
    def _assumptions_section() -> str:
        return f"""
<h2>Test Assumptions</h2>
<table>
<tr><th>Parameter</th><th>Assumed Value / Rationale</th></tr>
<tr><td>Input supply</td><td>+5.000 V @ max 5 A via Keithley 2230-30-1 CH1</td></tr>
<tr><td>Low-load current</td><td>10 % of rail Imax (avoids zero-load CCM artefacts)</td></tr>
<tr><td>High-load current</td><td>90 % of rail Imax (worst-case without OCP trip)</td></tr>
<tr><td>Transient frequency</td><td>{TRANSIENT_FREQ_HZ:.0f} Hz — 5 ms per half-period;
  fits inside 2 ms scope window per step edge</td></tr>
<tr><td>Captures per rail</td><td>{CAPTURES_PER_RAIL} (statistical sample for intermittent faults)</td></tr>
<tr><td>Scope time/div</td><td>200 µs/div · 2 ms total window · −500 µs pre-trigger</td></tr>
<tr><td>Trigger source</td><td>EXT (Keithley 2380 TRIG OUT → scope rear-panel EXT BNC)</td></tr>
<tr><td>Ripple crest factor</td><td>3.46× RMS → p-p (triangle wave, per buck converter model)</td></tr>
<tr><td>Settling criterion</td><td>±{SETTLING_BAND_PCT} % of Vnom for 50 consecutive samples</td></tr>
</table>"""

    @staticmethod
    def _summary_section(stats: Dict[str, dict]) -> str:
        rows = ""
        for rail, s in stats.items():
            pf_cls = "pass" if s["n_fail"] == 0 else "fail"
            pf_txt = "PASS"  if s["n_fail"] == 0 else "FAIL"
            settle_str = (
                f"{s['settle_mean_us']:.0f} / {s['settle_max_us']:.0f}"
                if s["settle_mean_us"] != float("inf")
                else "∞"
            )
            rows += f"""
<tr>
  <td><b>{rail}</b></td>
  <td>{s['dc_mean_v']:.4f} ± {s['dc_std_v']:.4f}</td>
  <td>{s['ripple_mean_mvpp']:.1f} / {s['ripple_max_mvpp']:.1f}</td>
  <td>{s['dev_mean_pct']:.2f} / {s['dev_max_pct']:.2f}</td>
  <td>{settle_str}</td>
  <td>{s['n_pass']} / {s['n_captures']}</td>
  <td class="{pf_cls}">{pf_txt}</td>
</tr>"""
        return f"""
<h2>Rail Summary</h2>
<table>
<tr>
  <th>Rail</th>
  <th>DC Voltage mean ± σ (V)</th>
  <th>Ripple mean / max (mVpp)</th>
  <th>Deviation mean / max (%)</th>
  <th>Settling mean / max (µs)</th>
  <th>Pass count</th>
  <th>Result</th>
</tr>
{rows}
</table>"""

    @staticmethod
    def _criteria_section() -> str:
        return f"""
<h2>Acceptance Criteria</h2>
<table>
<tr><th>Parameter</th><th>Limit</th><th>Source</th></tr>
<tr><td>DC output voltage accuracy</td>
    <td>Vnom ± 5 %</td>
    <td>Annexure — Test Parameters</td></tr>
<tr><td>Steady-state output ripple (Vpp)</td>
    <td>&lt; {MAX_RIPPLE_MVPP:.0f} mV</td>
    <td>Assessment specification</td></tr>
<tr><td>Peak transient voltage deviation</td>
    <td>&lt; ± {MAX_DEVIATION_PCT:.0f} % of Vnom</td>
    <td>Assumed: equals DC tolerance band</td></tr>
<tr><td>Settling time to ± 1 % of Vnom</td>
    <td>&lt; {MAX_SETTLING_US:.0f} µs</td>
    <td>Assumed: typical space-grade PDN budget</td></tr>
</table>"""

    @staticmethod
    def _detail_section(results: List[CaptureResult]) -> str:
        rows = ""
        for r in results:
            pf_cls     = "pass" if r.pass_fail == "PASS" else "fail"
            settle_str = (f"{r.settling_time_us:.0f}"
                          if r.settling_time_us != float("inf") else "∞")
            fail_txt   = "; ".join(r.fail_reasons) if r.fail_reasons else "—"
            rows += f"""
<tr>
  <td>{r.rail_name}</td>
  <td>{r.capture_index}</td>
  <td class="mono">{r.timestamp}</td>
  <td>{r.dc_voltage_v:.4f}</td>
  <td>{r.ripple_mvpp:.1f}</td>
  <td>{r.deviation_pct:.2f}</td>
  <td>{settle_str}</td>
  <td class="{pf_cls}">{r.pass_fail}</td>
  <td style="font-size:0.82em">{fail_txt}</td>
</tr>"""
        return f"""
<h2>Capture-Level Details</h2>
<table>
<tr>
  <th>Rail</th><th>#</th><th>Timestamp</th>
  <th>Vdc (V)</th><th>Ripple (mVpp)</th>
  <th>Deviation (%)</th><th>Settling (µs)</th>
  <th>P/F</th><th>Fail reason(s)</th>
</tr>
{rows}
</table>"""

    @staticmethod
    def _footer_section() -> str:
        return f"""
<footer>
  Generated by pdn_transient_test · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ·
  Digantara PDN Qualification Test Suite
</footer>"""
