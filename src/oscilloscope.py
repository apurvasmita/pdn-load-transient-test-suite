def save_waveform_csv(self, rail_name, cap_index, t_arr, v_arr, out_dir):
    import csv, pathlib
    fname = pathlib.Path(out_dir) / f"waveform_{rail_name}_{cap_index:02d}_{self._ts()}.csv"
    with open(fname, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['time_us', 'voltage_v'])
        w.writerows(zip(t_arr * 1e6, v_arr))
    return fname