"""
electronic_load.py
------------------
Driver for Keithley 2380 Series Programmable Electronic Load.

Used to apply and step the load current on each PDN output rail
during load-transient testing.

Transient mode overview
-----------------------
The load toggles between LOW current (10 % of Imax) and HIGH current
(90 % of Imax) at a fixed frequency via the internal transient generator.
The TRIG OUT BNC on the rear panel is asserted on every low→high edge;
this is wired to the oscilloscope external trigger input.

SCPI reference: Keithley 2380 Series Reference Manual 2380-901-01C.
"""

import time
import logging
from .base_instrument import BaseInstrument

logger = logging.getLogger(__name__)


class Keithley2380(BaseInstrument):
    """
    Constant-current electronic load with transient (dynamic) mode.

    Typical usage
    -------------
    eload = Keithley2380("GPIB0::8::INSTR")
    eload.connect()
    eload.configure_transient(low_i=0.25, high_i=2.25, freq_hz=100)
    eload.enable_input()
    ...
    eload.disable_input()
    eload.close()
    """

    def __init__(self, resource_str: str):
        super().__init__(resource_str, timeout_ms=10_000)

    # ------------------------------------------------------------------ #
    #  Transient (dynamic) CC mode                                         #
    # ------------------------------------------------------------------ #
    def configure_transient(self,
                             low_i: float,
                             high_i: float,
                             freq_hz: float = 100.0,
                             duty_cycle: float = 0.5):
        """
        Configure CC transient mode.

        Parameters
        ----------
        low_i      : steady-state low load current (A)
        high_i     : transient high load current (A)
        freq_hz    : toggle frequency (Hz) – default 100 Hz → 10 ms period
        duty_cycle : fraction of period spent at high_i (0.0–1.0)

        Notes
        -----
        With freq=100 Hz and duty=0.5:
          - 5 ms at low_i  (pre-transient baseline captured by scope)
          - 5 ms at high_i (transient dip captured by scope)
        Time/div = 200 µs → 2 ms capture window is inside the 5 ms window,
        so the waveform is fully captured without aliasing.
        """
        self.reset()
        self.write("FUNC CC")                           # constant-current mode
        self.write(f"CURR:TRAN:LOW {low_i:.4f}")        # low-level setpoint
        self.write(f"CURR:TRAN:HIGH {high_i:.4f}")      # high-level setpoint
        self.write(f"CURR:TRAN:FREQ {freq_hz:.2f}")     # toggle frequency
        self.write(f"CURR:TRAN:DCYC {duty_cycle:.3f}")  # duty cycle
        self.write("CURR:TRAN:STAT ON")                 # arm transient generator
        self.write("INP:STAT OFF")                      # leave input off until ready
        logger.info(
            "E-Load transient: low=%.3f A  high=%.3f A  %.1f Hz  DC=%.0f%%",
            low_i, high_i, freq_hz, duty_cycle * 100
        )

    def configure_static(self, current: float):
        """Set a fixed CC load (no transient). Useful for static DC tests."""
        self.reset()
        self.write("FUNC CC")
        self.write(f"CURR:LEV:IMM {current:.4f}")
        self.write("CURR:TRAN:STAT OFF")
        self.write("INP:STAT OFF")
        logger.info("E-Load static CC: %.4f A", current)

    # ------------------------------------------------------------------ #
    #  Input control                                                        #
    # ------------------------------------------------------------------ #
    def enable_input(self, settle_s: float = 0.3):
        self.write("INP:STAT ON")
        logger.info("E-Load input ON")
        time.sleep(settle_s)

    def disable_input(self):
        self.write("INP:STAT OFF")
        logger.info("E-Load input OFF")

    # ------------------------------------------------------------------ #
    #  Measurement                                                          #
    # ------------------------------------------------------------------ #
    def measure_voltage(self) -> float:
        return float(self.query("MEAS:VOLT?"))

    def measure_current(self) -> float:
        return float(self.query("MEAS:CURR?"))
