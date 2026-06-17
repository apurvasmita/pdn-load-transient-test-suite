"""
dmm.py
------
Driver for Keithley DMM6500 Digital Multimeter.

Used for two distinct measurements:
1. High-accuracy DC voltage on each PDN rail (NPLC=10 for noise rejection).
2. AC-coupled RMS voltage for steady-state ripple estimation.

SCPI reference: Keithley DMM6500 Reference Manual 077149901.

Ripple conversion note
----------------------
The DMM measures true RMS of the AC-coupled signal.  For a triangle-wave
ripple (typical switching regulator), Vpp ≈ 2√3 × Vrms ≈ 3.46 × Vrms.
For a practical mixed waveform this is conservative; we use 3.2 × Vrms as
the default Vpp estimator.  The oscilloscope Vpp reading takes precedence
for capture-level pass/fail; the DMM ripple is a quick sanity check.
"""

import logging
from .base_instrument import BaseInstrument

logger = logging.getLogger(__name__)

# Empirical crest-factor multiplier for switching-regulator ripple (triangle wave)
RIPPLE_CREST_FACTOR = 3.46


class KeithelyDMM6500(BaseInstrument):
    """
    Keithley DMM6500 high-resolution multimeter driver.

    Typical usage
    -------------
    dmm = KeithelyDMM6500("GPIB0::22::INSTR")
    dmm.connect()
    dmm.setup_dc_voltage(v_range=5.0, nplc=10)
    v = dmm.measure_dc_voltage()
    dmm.setup_ac_voltage(v_range=0.1)
    vrms = dmm.measure_ac_voltage()
    vpp_est = vrms * RIPPLE_CREST_FACTOR * 1000   # → mV
    """

    def __init__(self, resource_str: str):
        super().__init__(resource_str, timeout_ms=15_000)

    # ------------------------------------------------------------------ #
    #  DC voltage                                                           #
    # ------------------------------------------------------------------ #
    def setup_dc_voltage(self, v_range: float = 5.0, nplc: float = 10.0):
        """
        Configure for precise DC voltage measurement.

        Parameters
        ----------
        v_range : manual range in Volts (avoids ranging delays)
        nplc    : integration time in power-line cycles.
                  nplc=10 → 200 ms @ 50 Hz; rejects mains noise well.
        """
        self.reset()
        self.write("SENS:FUNC 'VOLT:DC'")
        self.write(f"SENS:VOLT:DC:RANG {v_range:.2f}")
        self.write(f"SENS:VOLT:DC:NPLC {nplc:.1f}")
        self.write("SENS:VOLT:DC:AZER:STAT ON")   # auto-zero for accuracy
        self.write("SENS:VOLT:DC:AVER:STAT OFF")  # no SW averaging needed at NPLC=10
        logger.info("DMM DC voltage mode: range=%.2f V  NPLC=%.1f", v_range, nplc)

    def measure_dc_voltage(self) -> float:
        """Return DC voltage in Volts."""
        v = float(self.query("MEAS:VOLT:DC?"))
        logger.debug("DMM Vdc = %.6f V", v)
        return v

    # ------------------------------------------------------------------ #
    #  AC voltage (ripple)                                                  #
    # ------------------------------------------------------------------ #
    def setup_ac_voltage(self, v_range: float = 0.1):
        """
        Configure for ripple (AC RMS) measurement.

        Parameters
        ----------
        v_range : 0.1 V range covers ripple up to ≈ 100 mVpp (70 mVrms)
                  which is well above the 50 mVpp spec limit.

        Bandwidth detector set to 20 Hz lower bound; upper bound is the DMM's
        default 300 kHz. This rejects DC and captures switching ripple
        (typically 100 kHz – 1 MHz range for these buck converters).
        """
        self.write("SENS:FUNC 'VOLT:AC'")
        self.write(f"SENS:VOLT:AC:RANG {v_range:.3f}")
        self.write("SENS:VOLT:AC:DET:BAND 20")    # 20 Hz lower cut-off
        logger.info("DMM AC voltage mode: range=%.3f V", v_range)

    def measure_ac_voltage(self) -> float:
        """Return AC-coupled RMS voltage in Volts."""
        v = float(self.query("MEAS:VOLT:AC?"))
        logger.debug("DMM Vac_rms = %.6f V  → Vpp_est = %.2f mVpp",
                     v, v * RIPPLE_CREST_FACTOR * 1000)
        return v

    def ripple_mvpp_estimate(self) -> float:
        """Convenience: measure and return estimated ripple in mVpp."""
        return self.measure_ac_voltage() * RIPPLE_CREST_FACTOR * 1000
