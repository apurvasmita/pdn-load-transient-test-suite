import pandas as pd
import matplotlib.pyplot as plt

# The summary file you uploaded
csv_file = 'transient_test_20260616_211933.csv'

# The 4 specific rails you want to plot
target_rails = ['+3V6', '+1V8', '+3V3', '+2V5']

try:
    print(f"Loading data from {csv_file}...")
    df = pd.read_csv(csv_file)
    
    # Create a 2x2 grid for the 4 rails
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    fig.suptitle('PDN Transient Stability Dashboard', fontsize=16, fontweight='bold', y=0.98)
    
    # Flatten the 2x2 axes array so we can loop through it easily
    axes = axes.flatten()
    
    for i, rail in enumerate(target_rails):
        ax = axes[i]
        
        # Filter the data for this specific rail
        rail_data = df[df['rail_name'] == rail]
        
        if rail_data.empty:
            ax.set_title(f"{rail} (No Data Found)", color='red')
            continue
            
        # Plot Vmax (Red), Vdc (Black), and Vmin (Blue)
        ax.plot(rail_data['capture_index'], rail_data['vmax_v'], 'r^--', label='V_max (Overshoot)', markersize=6)
        ax.plot(rail_data['capture_index'], rail_data['dc_voltage_v'], 'ko-', label='V_dc (Average)', markersize=4)
        ax.plot(rail_data['capture_index'], rail_data['vmin_v'], 'bv--', label='V_min (Undershoot)', markersize=6)
        
        # Formatting for each subplot
        ax.set_title(f'{rail} Rail Stability', loc='left', fontweight='bold', fontsize=12)
        ax.set_xlabel('Capture Index (Test Run)')
        ax.set_ylabel('Voltage (V)')
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.legend(loc='best', fontsize=9)

    # Adjust spacing so titles and labels don't overlap
    plt.tight_layout()
    plt.subplots_adjust(top=0.90) # Leave room for the main title
    
    print("Opening 2x2 Dashboard...")
    plt.show()

except FileNotFoundError:
    print(f"❌ Error: Could not find '{csv_file}'. Make sure it's in the same folder!")