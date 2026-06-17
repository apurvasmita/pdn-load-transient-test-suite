
import pandas as pd
import matplotlib.pyplot as plt

# 1. Point this to the exact CSV file you created earlier
csv_file = 'waveform_captures/waveform_3V3_test_01.csv'

try:
    # 2. Read the data
    print(f"Loading data from {csv_file}...")
    df = pd.read_csv(csv_file)

    # 3. Create the plot
    plt.figure(figsize=(10, 6))
    plt.plot(df['time_us'], df['voltage_v'], color='blue', linewidth=1.5)
    
    # 4. Add labels and grid
    plt.xlabel('Time (µs)')
    plt.ylabel('Voltage (V)')
    plt.title('3.3V Transient Waveform')
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # 5. Show the window!
    print("Opening plot window...")
    plt.show()

except FileNotFoundError:
    print(f"❌ Error: Could not find the file '{csv_file}'. Double-check the filename!")