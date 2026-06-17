"""
oscilloscope.py
---------------
Driver for Keysight DSOX6004A 4-Channel Oscilloscope.

Handles channel setup, triggering, waveform retrieval (BYTE), and
the oscilloscope's built-in measurements (Vpp, Vmax, Vmin, Vavg).

SCPI reference: Keysight InfiniiVision 6000 X-Series Programmer's Guide.

Trigger strategy
----------------
The Keithley 2380 TRIG OUT BNC fires on every low→high current edge.
Connect it to the scope's EXT BNC on the rear panel.
Trigger source is set to "EXT" with rising-edge detection at 1.5 V.
This gives a jitter-free trigger independent of the DUT voltage.

Alternative: If the TRIG OUT cable is unavailable, change trigger_source
to f"CHAN{channel}" with slope="NEG" and level = Vnom * 0.98 to trigger
on the leading-edge voltage droop.
"""

import time
import logging
import numpy as np
from .base_instrument import BaseInstrument

logger = logging.getLogger(__name__)


class KeysightDSOX6004A(BaseInstrument):
    """
    4-channel oscilloscope driver.

    Typical usage
    -------------
    scope = KeysightDSOX6004A("USB0::0x2A8D::0x9001::MY56310203::INSTR")
    scope.connect()
    scope.reset()
    scope.setup_channel(1, v_range=5.4, offset=3.6)   # +3V6 rail, ±50% headroom
    scope.setup_timebase(time_per_div=200e-6, delay=-500e-6)
    scope.setup_trigger(source="EXT", level=1.5, slope="POS")
    scope.single_trigger()
    scope.wait_for_trigger(timeout_s=5.0)
    t, v = scope.get_waveform(channel=1)
    """

    def __init__(self, resource_str: str):
        # Waveform download can be slow; give a 30 s timeout
        super().__init__(resource_str, timeout_ms=30_000)

    # ------------------------------------------------------------------ #
    #  Channel setup                                                        #
    # ------------------------------------------------------------------ #
    def setup_channel(self, channel: int, v_range: float,
                       coupling: str = "DC", offset: float = 0.0,
                       probe_atten: float = 1.0):
        """
        Configure one input channel.

        Parameters
        ----------
        channel     : 1-4
        v_range     : full vertical range in Volts (= 8 divs × V/div)
        coupling    : "DC" | "AC" | "GND"
        offset      : vertical offset in Volts (centre of screen)
        probe_atten : probe attenuation ratio (1, 10, 100 …)
        """
        ch = f"CHAN{channel}"
        self.write(f"{ch}:DISP ON")
        self.write(f"{ch}:RANG {v_range:.4f}")
        self.write(f"{ch}:COUP {coupling}")
        self.write(f"{ch}:OFFS {offset:.4f}")
        self.write(f"{ch}:PROB {probe_atten:.1f}")
        logger.info("Scope CH%d: range=%.3f V  offset=%.3f V  %s",
                    channel, v_range, offset, coupling)

    def disable_channel(self, channel: int):
        self.write(f"CHAN{channel}:DISP OFF")

    # ------------------------------------------------------------------ #
    #  Timebase                                                             #
    # ------------------------------------------------------------------ #
    def setup_timebase(self, time_per_div: float, delay: float = -500e-6):
        """
        Set time base.

        Parameters
        ----------
        time_per_div : seconds per division (10 divs total → full window)
        delay        : horizontal offset in seconds; negative = pre-trigger data
        """
        self.write(f"TIM:SCAL {time_per_div:.3e}")
        self.write(f"TIM:POS {delay:.3e}")
        logger.info("Scope timebase: %.1f µs/div  delay=%.0f µs",
                    time_per_div * 1e6, delay * 1e6)

    # ------------------------------------------------------------------ #
    #  Trigger                                                              #
    # ------------------------------------------------------------------ #
    def setup_trigger(self, source: str = "EXT",
                       level: float = 1.5,
                       slope: str = "POS"):
        """
        Configure edge trigger.

        Parameters
        ----------
        source : "EXT" (recommended) or "CHAN{n}"
        level  : trigger level in Volts
        slope  : "POS" (rising) or "NEG" (falling)
        """
        self.write("TRIG:MODE EDGE")
        self.write(f"TRIG:EDGE:SOUR {source}")
        self.write(f"TRIG:EDGE:LEV {level:.4f}")
        self.write(f"TRIG:EDGE:SLOP {slope}")
        logger.info("Scope trigger: %s  %.3f V  %s edge", source, level, slope)

    # ------------------------------------------------------------------ #
    #  Acquisition                                                          #
    # ------------------------------------------------------------------ #
    def set_acquisition_mode(self, mode: str = "NORM", n_avg: int = 1):
        """
        mode : "NORM" | "AVER" | "HRES"
        n_avg: used only when mode="AVER"
        """
        self.write(f"ACQ:TYPE {mode}")
        if mode == "AVER":
            self.write(f"ACQ:COUN {n_avg}")

    def single_trigger(self):
        """Arm the scope for one triggered acquisition."""
        self.write(":SING")

    def wait_for_trigger(self, timeout_s: float = 10.0) -> bool:
        """
        Poll the Acquisition Event Register (AER) bit 0 until set,
        indicating the acquisition is complete.

        Raises TimeoutError if no trigger within timeout_s.
        """
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            # :AER? reads and clears the Acquisition Event Register
            # Bit 0 = acquisition complete
            aer = int(self.query(":AER?"))
            if aer & 1:
                logger.debug("Scope triggered after %.0f ms",
                             (time.time() - t0) * 1000)
                return True
            time.sleep(0.05)
        raise TimeoutError(
            f"Oscilloscope [{self.resource_str}] did not trigger "
            f"within {timeout_s:.0f} s"
        )

    # ------------------------------------------------------------------ #
    #  Built-in measurements                                               #
    # ------------------------------------------------------------------ #
    def measure_vpp(self, channel: int) -> float:
        """Peak-to-peak voltage (V)."""
        return float(self.query(f":MEAS:VPP? CHAN{channel}"))

    def measure_vmax(self, channel: int) -> float:
        return float(self.query(f":MEAS:VMAX? CHAN{channel}"))

    def measure_vmin(self, channel: int) -> float:
        return float(self.query(f":MEAS:VMIN? CHAN{channel}"))

    def measure_vavg(self, channel: int) -> float:
        """Display-area average voltage (V)."""
        return float(self.query(f":MEAS:VAV? DISP,CHAN{channel}"))

    # ------------------------------------------------------------------ #
    #  Waveform download                                                    #
    # ------------------------------------------------------------------ #
    def get_waveform(self, channel: int) -> tuple[np.ndarray, np.ndarray]:
        """
        Download waveform data for the specified channel.

        Returns
        -------
        t : np.ndarray  time axis in seconds (t=0 at trigger point)
        v : np.ndarray  voltage axis in Volts

        Implementation notes
        --------------------
        BYTE format transfers 8-bit unsigned integers which are converted to
        engineering units using the preamble scaling coefficients:
            V = (raw - Yref) * Yinc + Yorg
            t = (sample_index - Xref) * Xinc + Xorg
        """
        self.write(f":WAV:SOUR CHAN{channel}")
        self.write(":WAV:FORM BYTE")
        self.write(":WAV:UNS ON")
        self.write(":WAV:POIN:MODE NORM")

        # Preamble: 10 comma-separated fields
        pre = self.query(":WAV:PRE?").split(",")
        n_points = int(pre[2])
        x_inc    = float(pre[4])
        x_orig   = float(pre[5])
        x_ref    = float(pre[6])
        y_inc    = float(pre[7])
        y_orig   = float(pre[8])
        y_ref    = float(pre[9])

        raw = np.array(
            self.inst.query_binary_values(":WAV:DATA?", datatype="B"),
            dtype=np.float64
        )

        v = (raw - y_ref) * y_inc + y_orig
        t = (np.arange(n_points) - x_ref) * x_inc + x_orig

        logger.debug("Waveform CH%d: %d points  Xinc=%.3e s", channel, n_points, x_inc)
        return t, v
