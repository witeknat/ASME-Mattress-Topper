import serial
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button, Slider
import re
import time
from matplotlib.colors import LinearSegmentedColormap
from matplotlib import rcParams

# ===== CONFIGURATION =====
SERIAL_PORT = 'COM5'
SERIAL_BAUD = 9600
GRID_SIZE = 4
REFRESH_RATE = 50  # Animation refresh rate in ms
AVERAGE_UPDATE_INTERVAL = 0.5  # How often to update averages (seconds)

# ===== STYLE SETTINGS =====
plt.style.use('dark_background')

# Modern color scheme
DARK_BG = '#111111'
PANEL_BG = '#1D1E2C'
ACCENT_COLOR = '#5D7FBF'
TEXT_COLOR = '#FFFFFF'
MUTED_TEXT = '#AAAAAA'
HIGHLIGHT_COLOR = '#3498db'

# Configure matplotlib
rcParams['font.family'] = 'sans-serif'
rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
rcParams['axes.facecolor'] = PANEL_BG
rcParams['figure.facecolor'] = DARK_BG

# ===== SENSOR MAPPING =====
# Custom mapping for the 4x4 grid
# Format: [sensor_type, index]
SENSOR_MAPPING = [
    # Row 1 (was Row 1)
    [("A0", 1), ("A0", 0), ("Analog", 6), ("Analog", 7)],
    # Row 2 (was Row 2)
    [("A0", 3), ("A0", 2), ("Analog", 4), ("Analog", 5)],
    # Row 3 (was Row 3)
    [("A0", 5), ("A0", 4), ("Analog", 2), ("Analog", 3)],
    # Row 4 (was Row 4)
    [("A0", 7), ("A0", 6), ("Analog", 0), ("Analog", 1)]
]

# ===== COLOR MAP =====
# Beautiful gradient from blue (low pressure) to red (high pressure)
colors = [
    (0.0, '#050838'),      # Very dark blue for zero pressure
    (0.1, '#0C1B7D'),      # Dark blue for low pressure
    (0.3, '#1560BD'),      # Medium blue
    (0.45, '#39A7FF'),     # Light blue
    (0.6, '#FFDE59'),      # Yellow
    (0.75, '#FF914D'),     # Orange
    (0.9, '#FF3333'),      # Red
    (1.0, '#990000')       # Dark red for maximum pressure
]
pressure_cmap = LinearSegmentedColormap.from_list('pressure_cmap', colors, N=256)

# ===== HELPER FUNCTIONS =====
def calculate_weighted_pressure_average(pressures, durations):
    """Calculate weighted average pressure based on pressure values and their durations."""
    if not pressures or not durations or len(pressures) != len(durations):
        return 0
    
    weighted_sum = sum(pressure * duration for pressure, duration in zip(pressures, durations))
    total_duration = sum(durations)
    
    return weighted_sum / total_duration if total_duration > 0 else 0

class PressureSensorVisualizer:
    def __init__(self):
        self.ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=0.1)
        
        # Initialize data storage
        self.data = np.zeros((GRID_SIZE, GRID_SIZE))
        self.a0_values = [0] * 8
        self.analog_values = [0] * 8
        self.a0_timestamps = [time.time()] * 8
        self.analog_timestamps = [time.time()] * 8
        
        # Time tracking
        self.start_time = time.time()
        self.last_average_update = time.time()
        
        # Pressure history and weighted averages
        self.pressure_history = {
            'A0': [[] for _ in range(8)],
            'Analog': [[] for _ in range(8)]
        }
        self.weighted_averages = {
            'A0': [0] * 8,
            'Analog': [0] * 8
        }
        
        # Statistics
        self.peak_values = np.zeros((GRID_SIZE, GRID_SIZE))
        self.view_mode = 'current'  # Options: 'current', 'average', 'peak'
        
        # Configure the visualization
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the visualization UI"""
        # Create figure with better proportions
        self.fig = plt.figure(figsize=(12, 8), dpi=100)
        self.fig.patch.set_facecolor(DARK_BG)
        
        # Create layout grid
        gs = self.fig.add_gridspec(1, 12)
        
        # Main heatmap area (spans 9 columns)
        self.ax_main = self.fig.add_subplot(gs[0, :9])
        
        # Controls area (spans 3 columns)
        self.ax_controls = self.fig.add_subplot(gs[0, 9:])
        self.ax_controls.axis('off')
        
        # Initialize heatmap
        self.heatmap = self.ax_main.imshow(
            self.data, 
            cmap=pressure_cmap, 
            vmin=0, 
            vmax=250, 
            interpolation="gaussian"
        )
        
        # Style the grid
        self.ax_main.set_xticks(np.arange(-0.5, GRID_SIZE, 1), minor=True)
        self.ax_main.set_yticks(np.arange(-0.5, GRID_SIZE, 1), minor=True)
        self.ax_main.grid(which="minor", color="#333333", linestyle='-', linewidth=0.5)
        self.ax_main.tick_params(which="both", bottom=False, left=False, labelbottom=False, labelleft=False)
        
        # Add sensor position labels
        for i in range(GRID_SIZE):
            self.ax_main.text(-0.5, i, f"{i+1}", color=TEXT_COLOR, ha='center', va='center', fontsize=10)
            self.ax_main.text(i, -0.5, f"{i+1}", color=TEXT_COLOR, ha='center', va='center', fontsize=10)
        
        # Add value annotations
        self.text_annotations = [
            [self.ax_main.text(j, i, "0", ha='center', va='center', color=TEXT_COLOR, 
                       fontsize=12, fontweight='bold')
             for j in range(GRID_SIZE)] for i in range(GRID_SIZE)
        ]
        
        # Add time annotations (smaller and more subtle)
        self.time_annotations = [
            [self.ax_main.text(j, i + 0.25, "0.0s", ha='center', va='center', 
                       color=MUTED_TEXT, fontsize=8)
             for j in range(GRID_SIZE)] for i in range(GRID_SIZE)
        ]
        
        # Add weighted average annotations
        self.avg_annotations = [
            [self.ax_main.text(j, i + 0.4, "Avg: 0", ha='center', va='center', 
                      color=HIGHLIGHT_COLOR, fontsize=8)
             for j in range(GRID_SIZE)] for i in range(GRID_SIZE)
        ]
        
        # Add title
        self.title = self.fig.suptitle(
            "Pressure Sensor Array", 
            fontsize=16, 
            fontweight='bold',
            color=TEXT_COLOR,
            y=0.97
        )
        
        # Add timer display
        self.timer_text = self.fig.text(
            0.05, 0.02, 
            "Time: 0.0s", 
            ha='left', 
            color=TEXT_COLOR, 
            fontsize=10
        )
        
        # Add colorbar
        cbar = plt.colorbar(self.heatmap, ax=self.ax_main, pad=0.02, shrink=0.8)
        cbar.set_label("Pressure", color=TEXT_COLOR, fontsize=10)
        plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color=TEXT_COLOR)
        
        # Add view mode selector in control panel
        self.mode_button_axes = []
        modes = [('Current', 'current'), ('Average', 'average'), ('Peak', 'peak')]
        
        for i, (mode_label, mode_val) in enumerate(modes):
            btn_ax = plt.axes([0.82, 0.85 - (i * 0.07), 0.15, 0.05])
            self.mode_button_axes.append(btn_ax)
        
        self.mode_btns = []
        for i, (mode_label, mode_val) in enumerate(modes):
            color = ACCENT_COLOR if mode_val == self.view_mode else PANEL_BG
            btn = Button(
                self.mode_button_axes[i], 
                mode_label, 
                color=color, 
                hovercolor='#666666'
            )
            btn.label.set_color(TEXT_COLOR)
            btn.on_clicked(lambda event, m=mode_val: self.change_view_mode(m))
            self.mode_btns.append(btn)
        
        # Add reset button
        self.reset_ax = plt.axes([0.82, 0.05, 0.15, 0.06])
        self.reset_button = Button(
            self.reset_ax, 
            'RESET', 
            color='#AA3333', 
            hovercolor='#FF5555'
        )
        self.reset_button.label.set_color('white')
        self.reset_button.label.set_fontweight('bold')
        self.reset_button.on_clicked(self.reset)
        
        # Add sensor information panel
        self.info_text = self.ax_controls.text(
            0.5, 0.5,
            "Sensor Information\n\nView Mode: Current\n\nClick on a sensor\nto view details",
            ha='center',
            va='center',
            color=TEXT_COLOR,
            fontsize=10,
            transform=self.ax_controls.transAxes
        )
        
        # Add version info
        self.fig.text(
            0.98, 0.02, 
            "v2.0", 
            ha='right', 
            color=MUTED_TEXT, 
            fontsize=8,
            fontstyle='italic'
        )
        
        # Make the plot interactive
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
    
    def on_click(self, event):
        """Handle click events on the heatmap"""
        if event.inaxes == self.ax_main:
            # Get the clicked cell
            i, j = int(round(event.ydata)), int(round(event.xdata))
            if 0 <= i < GRID_SIZE and 0 <= j < GRID_SIZE:
                sensor_type, index = SENSOR_MAPPING[i][j]
                current_value = self.data[i][j]
                avg_value = self.weighted_averages[sensor_type][index]
                peak_value = self.peak_values[i][j]
                
                # Update info panel
                info_text = (
                    f"Sensor: {sensor_type}[{index}]\n\n"
                    f"Current: {int(current_value)}\n"
                    f"Average: {avg_value:.1f}\n"
                    f"Peak: {int(peak_value)}\n\n"
                    f"Position: ({i+1},{j+1})"
                )
                self.info_text.set_text(info_text)
    
    def change_view_mode(self, mode):
        """Change the visualization mode"""
        self.view_mode = mode
        
        # Update button colors
        for i, (_, mode_val) in enumerate([('Current', 'current'), ('Average', 'average'), ('Peak', 'peak')]):
            self.mode_btns[i].color = ACCENT_COLOR if mode_val == self.view_mode else PANEL_BG
            self.mode_btns[i].hovercolor = '#666666'
        
        # Update info panel
        self.info_text.set_text(f"Sensor Information\n\nView Mode: {self.view_mode.capitalize()}\n\nClick on a sensor\nto view details")
    
    def reset(self, event=None):
        """Reset all data and statistics"""
        # Reset data to zeros
        self.data = np.zeros((GRID_SIZE, GRID_SIZE))
        self.a0_values = [0] * 8
        self.analog_values = [0] * 8
        
        # Reset timestamps
        current_time = time.time()
        self.start_time = current_time
        self.a0_timestamps = [current_time] * 8
        self.analog_timestamps = [current_time] * 8
        
        # Reset pressure history and weighted averages
        self.pressure_history = {
            'A0': [[] for _ in range(8)],
            'Analog': [[] for _ in range(8)]
        }
        self.weighted_averages = {
            'A0': [0] * 8,
            'Analog': [0] * 8
        }
        
        # Reset peak values
        self.peak_values = np.zeros((GRID_SIZE, GRID_SIZE))
        
        # Reset all text annotations
        for i in range(GRID_SIZE):
            for j in range(GRID_SIZE):
                self.text_annotations[i][j].set_text("0")
                self.time_annotations[i][j].set_text("0.0s")
                self.avg_annotations[i][j].set_text("Avg: 0")
        
        # Update timer display
        self.timer_text.set_text("Time: 0.0s")
        
        # Update info panel
        self.info_text.set_text(f"Sensor Information\n\nView Mode: {self.view_mode.capitalize()}\n\nClick on a sensor\nto view details")
    
    def update(self, frame):
        """Update the visualization with new data from serial"""
        current_time = time.time()
        total_time = current_time - self.start_time
        
        # Update timer display
        self.timer_text.set_text(f"Time: {total_time:.1f}s")
        
        # Read all available lines from serial
        while self.ser.in_waiting > 0:
            line = self.ser.readline().decode('utf-8', errors='replace').strip()
            
            # Check for A0 values
            a0_match = re.search(r'A0 Value\[(\d+)\] = (\d+)', line)
            if a0_match:
                index = int(a0_match.group(1))
                value = int(a0_match.group(2))
                
                # Special handling for A0[1]
                if index == 1:
                    value = value / 4.5
                    if (value > 50):
                        value = 50
                    else:
                        value = 0
                
                if 0 <= index < 8:
                    # If value changed, update history
                    if self.a0_values[index] != value:
                        # Calculate duration of previous pressure value
                        duration = current_time - self.a0_timestamps[index]
                        
                        # Add previous value and its duration to history
                        self.pressure_history['A0'][index].append((self.a0_values[index], duration))
                        
                        # Update timestamp for new value
                        self.a0_timestamps[index] = current_time
                        
                        # Update the current value
                        self.a0_values[index] = value
                        
                        # Calculate weighted average
                        if self.pressure_history['A0'][index]:
                            pressures = [p[0] for p in self.pressure_history['A0'][index]]
                            durations = [p[1] for p in self.pressure_history['A0'][index]]
                            self.weighted_averages['A0'][index] = calculate_weighted_pressure_average(pressures, durations)
            
            # Check for Analog values
            analog_match = re.search(r'Analog Value\[(\d+)\] = (\d+)', line)
            if analog_match:
                index = int(analog_match.group(1))
                value = int(analog_match.group(2))
                if 0 <= index < 8:
                    # If value changed, update history
                    if self.analog_values[index] != value:
                        # Calculate duration of previous pressure value
                        duration = current_time - self.analog_timestamps[index]
                        
                        # Add previous value and its duration to history
                        self.pressure_history['Analog'][index].append((self.analog_values[index], duration))
                        
                        # Update timestamp for new value
                        self.analog_timestamps[index] = current_time
                        
                        # Update the current value
                        self.analog_values[index] = value
                        
                        # Calculate weighted average
                        if self.pressure_history['Analog'][index]:
                            pressures = [p[0] for p in self.pressure_history['Analog'][index]]
                            durations = [p[1] for p in self.pressure_history['Analog'][index]]
                            self.weighted_averages['Analog'][index] = calculate_weighted_pressure_average(pressures, durations)
        
        # Periodically update weighted averages even if values don't change
        if current_time - self.last_average_update >= AVERAGE_UPDATE_INTERVAL:
            # Update weighted averages for all sensors
            for index in range(8):
                # For A0 sensors
                if self.pressure_history['A0'][index]:
                    temp_history = self.pressure_history['A0'][index].copy()
                    current_duration = current_time - self.a0_timestamps[index]
                    if current_duration > 0:
                        temp_history.append((self.a0_values[index], current_duration))
                    
                    pressures = [p[0] for p in temp_history]
                    durations = [p[1] for p in temp_history]
                    self.weighted_averages['A0'][index] = calculate_weighted_pressure_average(pressures, durations)
                
                # For Analog sensors
                if self.pressure_history['Analog'][index]:
                    temp_history = self.pressure_history['Analog'][index].copy()
                    current_duration = current_time - self.analog_timestamps[index]
                    if current_duration > 0:
                        temp_history.append((self.analog_values[index], current_duration))
                    
                    pressures = [p[0] for p in temp_history]
                    durations = [p[1] for p in temp_history]
                    self.weighted_averages['Analog'][index] = calculate_weighted_pressure_average(pressures, durations)
            
            self.last_average_update = current_time
        
        # Build the data grid according to the view mode
        display_data = np.zeros((GRID_SIZE, GRID_SIZE))
        
        for i in range(GRID_SIZE):
            for j in range(GRID_SIZE):
                sensor_type, index = SENSOR_MAPPING[i][j]
                
                # Get current value
                if sensor_type == "A0":
                    current_value = self.a0_values[index]
                    time_since_change = current_time - self.a0_timestamps[index]
                    avg = self.weighted_averages['A0'][index]
                else:  # "Analog"
                    current_value = self.analog_values[index]
                    time_since_change = current_time - self.analog_timestamps[index]
                    avg = self.weighted_averages['Analog'][index]
                
                # Update peak value
                if current_value > self.peak_values[i][j]:
                    self.peak_values[i][j] = current_value
                
                # Select which value to display based on view mode
                if self.view_mode == 'current':
                    display_data[i][j] = current_value
                elif self.view_mode == 'average':
                    display_data[i][j] = avg
                elif self.view_mode == 'peak':
                    display_data[i][j] = self.peak_values[i][j]
                
                # Update the annotations
                self.text_annotations[i][j].set_text(f"{int(display_data[i][j])}")
                self.time_annotations[i][j].set_text(f"{time_since_change:.1f}s")
                self.avg_annotations[i][j].set_text(f"Avg: {avg:.1f}")
                
                # Adjust text color based on value for better readability
                val = display_data[i][j]
                if val > 700:
                    self.text_annotations[i][j].set_color('white')
                elif val > 300:
                    self.text_annotations[i][j].set_color('black')
                else:
                    self.text_annotations[i][j].set_color('white')
        
        # Update the actual data
        self.data = display_data
        
        # Update the heatmap
        self.heatmap.set_data(display_data)
        
        # Return the updated artists
        return [self.heatmap] + [ann for row in self.text_annotations for ann in row] + \
               [ann for row in self.time_annotations for ann in row] + \
               [ann for row in self.avg_annotations for ann in row]
    
    def run(self):
        """Run the visualization"""
        # Set up animation
        self.animation = animation.FuncAnimation(
            self.fig, 
            self.update, 
            interval=REFRESH_RATE, 
            blit=False, 
            cache_frame_data=False
        )
        
        # Show the plot
        plt.tight_layout()
        plt.subplots_adjust(left=0.05, right=0.95, top=0.92, bottom=0.05)
        plt.show()

# Run the application
if __name__ == "__main__":
    visualizer = PressureSensorVisualizer()
    visualizer.run()
