import pyvisa
import numpy as np
import pandas as pd
from datetime import datetime
import os

# ── Config ──────────────────────────────────────────
SCOPE_ADDR  = "USB0::0x0699::0x0413::C012345::INSTR"  # ← your address here
CHANNEL     = "CH1"
SAVE_FOLDER = "waveform_captures"
os.makedirs(SAVE_FOLDER, exist_ok=True)

# ── Connect ─────────────────────────────────────────
rm    = pyvisa.ResourceManager()
scope = rm.open_resource(SCOPE_ADDR)
scope.timeout = 10000  # 10 seconds

# ── Configure scope ──────────────────────────────────
scope.write("*RST")
scope.write(f"{CHANNEL}:SCALe 1.0")       # 1V/div
scope.write(f"{CHANNEL}:OFFSet 0")
scope.write("TIMebase:SCALe 200E-6")       # 200 µs/div
scope.write("ACQuire:SAMPlingrate 1E7")    # 10 MSa/s
scope.write("ACQuire:STATE RUN")

# ── Wait for single trigger ──────────────────────────
scope.write("TRIGger:A:EDGE:SOURce CH1")
scope.write("TRIGger:A:LEVel 0.1")
scope.write("ACQuire:STOPAfter SEQuence")  # single capture
scope.write("ACQuire:STATE RUN")
scope.query("*OPC?")                       # wait until done

# ── Read waveform data ───────────────────────────────
scope.write("DATa:SOUrce CH1")
scope.write("DATa:ENCdg RIBinary")        # signed binary
scope.write("DATa:WIDth 2")              # 2 bytes per sample
scope.write("WFMOutpre:BYT_Or MSB")

# Read scaling factors from scope
x_incr   = float(scope.query("WFMOutpre:XINcr?"))
x_zero   = float(scope.query("WFMOutpre:XZEro?"))
y_mult   = float(scope.query("WFMOutpre:YMUlt?"))
y_zero   = float(scope.query("WFMOutpre:YZEro?"))
y_off    = float(scope.query("WFMOutpre:YOFf?"))

# Pull the raw binary data
raw = scope.query_binary_values("CURVe?", datatype='h', is_big_endian=True)

# ── Convert raw ADC → real voltage & time ────────────
samples  = np.array(raw)
time_s   = x_zero + np.arange(len(samples)) * x_incr
voltage  = (samples - y_off) * y_mult + y_zero

time_us  = time_s * 1e6   # convert to microseconds

# ── Attach timestamp & save ──────────────────────────
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename  = f"{SAVE_FOLDER}/waveform_{CHANNEL}_{timestamp}.csv"

df = pd.DataFrame({
    "timestamp":  timestamp,           # same for all rows — capture time
    "time_us":    time_us,
    "voltage_v":  voltage
})

df.to_csv(filename, index=False)
print(f"✅ Saved: {filename}  ({len(df)} samples)")