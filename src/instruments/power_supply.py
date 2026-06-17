"""
power_supply.py
---------------
Driver for Keithley 2230-30-1 Triple-Channel DC Power Supply.
Provides the +5 V regulated input to the PDN under test.

SCPI reference: Keithley 2230-30-1 Series Reference Manual Rev A.
"""

import time
import logging
from .base_instrument import BaseInstrument

logger = logging.getLogger(__name__)


class Keithley2230(BaseInstrument):
    """
    Controls a single channel of the Keithley 2230-30-1.

    Typical usage
    -------------
    psu = Keithley2230("GPIB0::5::INSTR")
    psu.connect()
    psu.configure(channel=1, voltage=5.0, current_limit=5.0)
    psu.enable_output()
    ...
    psu.disable_output()
    psu.close()
    """

    def __init__(self, resource_str: str):
        super().__init__(resource_str, timeout_ms=10_000)

    # ------------------------------------------------------------------ #
    #  Configuration                                                        #
    # ------------------------------------------------------------------ #
    def configure(self, channel: int = 1,
                  voltage: float = 5.0,
                  current_limit: float = 5.0):
        """
        Configure a channel and leave output OFF.

        Parameters
        ----------
        channel       : 1 / 2 / 3
        voltage       : set-point in Volts
        current_limit : over-current protection in Amperes
        """
        self.reset()
        self.write(f"INST:SEL CH{channel}")
        self.write(f"VOLT {voltage:.4f}")
        self.write(f"CURR {current_limit:.4f}")
        self.write("OUTP:ALL:STAT OFF")
        logger.info("PSU CH%d configured: %.3f V / %.3f A limit",
                    channel, voltage, current_limit)

    # ------------------------------------------------------------------ #
    #  Output control                                                       #
    # ------------------------------------------------------------------ #
    def enable_output(self, settle_s: float = 1.0):
        """Turn all outputs ON and wait for rails to settle."""
        self.write("OUTP:ALL:STAT ON")
        logger.info("PSU output ON  (settling %.1f s)", settle_s)
        time.sleep(settle_s)

    def disable_output(self):
        self.write("OUTP:ALL:STAT OFF")
        logger.info("PSU output OFF")

    # ------------------------------------------------------------------ #
    #  Measurement                                                          #
    # ------------------------------------------------------------------ #
    def measure_voltage(self, channel: int = 1) -> float:
        self.write(f"INST:SEL CH{channel}")
        v = float(self.query("MEAS:VOLT?"))
        logger.debug("PSU CH%d Vmeas = %.5f V", channel, v)
        return v

    def measure_current(self, channel: int = 1) -> float:
        self.write(f"INST:SEL CH{channel}")
        i = float(self.query("MEAS:CURR?"))
        logger.debug("PSU CH%d Imeas = %.5f A", channel, i)
        return i
