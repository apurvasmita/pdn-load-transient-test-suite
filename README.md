# PDN Load Transient Test Suite

Load transient testing automation software suite for Digantara satellite payload power distribution network (PDN) to be used for Junior Hardware Test Engineer examination (Question 2a).

This program controls four lab equipment over SCPI/PyVISA protocol and conducts structured load transient test on all four rail voltages, providing CSV file with time stamp as well as HTML report.

---

## Table of Contents

- [Introduction](#introduction)
- [Hardware Under Test](#hardware-under-test)
- [Laboratory Tools](#laboratory-tools)
- [Criteria for Acceptance](#criteria-for-acceptance)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Operation](#operation)
- [Testing Process](#testing-process)
- [Output Files](#output-files)

---

## Introduction

The PDN provides four outputs, based on a **regulated +5V** input and DC-DC Buck converter followed by LDOs. Power-up sequencing goes via a PGood daisy chain. The test performs qualification for each output against transients loads (100Hz), taking ten waveforms per rail and analyzing for ripple, peak deviation, and settling time relative to the flight acceptance requirements.

In addition, there is a **dry run** capability for testing off-line or in CI. This option creates a dummy dataset that simulates the SN-017 +3V3 problem discussed in Question 2b.

---
## Hardware Under Test

| Rail  | Vnom (V) | Tolerance | Imax (A) | Scope CH |
|-------|----------|-----------|----------|----------|
| +3V6  | 3.6      | ± 5 %     | 2.5      | CH1      |
| +1V8  | 1.8      | ± 5 %     | 3.0      | CH2      |
| +3V3  | 3.3      | ± 5 %     | 3.0      | CH3      |
| +2V5  | 2.5      | ± 5 %     | 1.5      | CH4      |

---

## Laboratory Equipment

| # | Device        | Model              |
|---|--------------|--------------------|
| 1 | DC Programmable Power Supply     | Keithley 2230-30-1   |
| 2 | Electronic Programmable Load     | Keithley 2380-500-15  |
| 3 | Oscilloscope                     | Keysight DSOX6004A   |
| 4 | Digital Multimeter 

### Instrument Connectors

```
Keithley 2230-30-1 CH1  ──►  PDN +5V input (VIN)
Keithley 2380 (load)    ──►  PDN rail under test (each one individually)
Keithley 2380 TRIG OUT  ──►  Scope rear panel EXT BNC port
Scope CH1-CH4 probes    ──►  +3V6 / +1V8 / +3V3 / +2V5 rail test points
Keithley DMM6500 HI     ──►  Test rail (along with E-load clips)
```

> All instruments require common GND connections.

## Criteria for Acceptance

| Parameter | Limit |
|-----------|-------|
| DC output voltage accuracy | Vnom ± 5 % |
| Steady-state ripple (Vpp) | < 50 mV |
| Peak transient deviation | < ± 5 % of Vnom |
| Settling time (to ± 1 % of Vnom) | < 500 µs |

Load profile 

| Phase | Current | Purpose |
|-------|---------|---------|
| Low   | 10 % of Imax | Pre-transient baseline |
| High  | 90 % of Imax | Worst-case load step |

Transient generator runs at **100 Hz, 50 % duty cycle** — that's 5 ms low, 5 ms high per cycle.

---

## Project Structure

```
pdn_transient_test/
├── main.py                         
├── requirements.txt                
├── config/
│   └── test_config.yaml            
└── src/
    ├── __init__.py
    ├── instruments/
    │   ├── __init__.py
    │   ├── base_instrument.py       # VISA wrapper: connect / write / query / reset / close
    │   ├── power_supply.py          # Keithley 2230-30-1 driver
    │   ├── electronic_load.py       # Keithley 2380 transient CC mode driver
    │   ├── oscilloscope.py          # Keysight DSOX6004A waveform download + measurements
    │   └── dmm.py                   # Keithley DMM6500 DC + AC-RMS driver
    ├── test_sequence.py          
    ├── data_logger.py             
    └── report_generator.py        

```
## Testing Process

Number of runs per rail, in sequence (+3V6 → +1V8 → +3V3 → +2V5):
1. PSU CH1 set to +5.000 V / 5 A, output ON
2. E-load settings: transient CC mode, 100 Hz, 50 % duty cycle
      Low current = 10 % of Imax   (baseline)
      High current = 90 % of Imax   (worst case step)
3. Scope CH configuration: VRANGE=1.5×Vnom, DC coupling, 200 µs/div
4. Trigger: EXT, on E-load TRIG OUT signal, rising edge, threshold=1.5 V
5. Enable E-load inputs
6. For each of 10 runs:
      a. Scope armed (:SING)
      b. Wait for AER=bit 0 (scope ready), 5 s timeout
      c. Download BYTE encoded waveforms with :WAV:DATA?
      d. Scope measurements (VPP, Vmax, Vmin)
      e. Multimeter readings (DCV NPLC=10) & AC RMS
      f. Calculate settling time based on np array
      g. Pass/fail test result logging into CSV file
7. Disable E-load inputs
8. Operator prompts to test next rail


## Output Files


transient_test_<ts>.csv - All 40 capture measurements + Pass/Fail 

pdn_transient_report_<ts>.html-Self - contained HTML test report 

run_<ts>.log - Full console + SCPI debug log 
