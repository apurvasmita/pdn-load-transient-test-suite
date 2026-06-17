"""
base_instrument.py
------------------
Abstract base class for all SCPI instruments.
Wraps pyvisa resource with logging, timeout, and error-check helpers.
"""

import logging
import pyvisa

logger = logging.getLogger(__name__)


class BaseInstrument:
    def __init__(self, resource_str: str, timeout_ms: int = 10_000):
        self.resource_str = resource_str
        self.timeout_ms = timeout_ms
        self.inst: pyvisa.resources.Resource | None = None

    # ------------------------------------------------------------------ #
    #  Connection                                                          #
    # ------------------------------------------------------------------ #
    def connect(self) -> str:
        rm = pyvisa.ResourceManager()
        self.inst = rm.open_resource(self.resource_str)
        self.inst.timeout = self.timeout_ms
        idn = self.query("*IDN?").strip()
        logger.info("Connected: %s  →  %s", self.resource_str, idn)
        return idn

    def close(self):
        if self.inst:
            self.inst.close()
            logger.info("Closed: %s", self.resource_str)

    # ------------------------------------------------------------------ #
    #  Low-level SCPI helpers                                              #
    # ------------------------------------------------------------------ #
    def write(self, cmd: str):
        logger.debug("W [%s] %s", self.resource_str, cmd)
        self.inst.write(cmd)

    def query(self, cmd: str) -> str:
        logger.debug("Q [%s] %s", self.resource_str, cmd)
        return self.inst.query(cmd)

    def query_binary(self, cmd: str, datatype: str = "B") -> list:
        """Return raw binary payload (e.g. waveform bytes)."""
        logger.debug("QB [%s] %s", self.resource_str, cmd)
        return self.inst.query_binary_values(cmd, datatype=datatype)

    def reset(self):
        self.write("*RST")
        self.write("*CLS")
        logger.info("Reset: %s", self.resource_str)

    def check_error(self):
        """Read :SYST:ERR? and raise if non-zero."""
        resp = self.query(":SYST:ERR?").strip()
        if not resp.startswith("+0") and not resp.startswith("0,"):
            raise RuntimeError(f"Instrument error [{self.resource_str}]: {resp}")
