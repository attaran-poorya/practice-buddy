"""Visualization functions for Practice Buddy Bot"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from scipy import signal
from config import VIZ_PARAMS, METRONOME_PARAMS


def visualize_metronome_detection(y, sr, beat_times, filepath):
    """Create visualization of waveform with detected beats highlighted"""
    try:
        # Create time array for x-axis
        duration = len(y) / sr
        time = np.linspace(0, duration, len(y))
        
        # Create figure with 2 subplots
        fig, (ax1, ax2) = plt.subplots(
            2, 1, 
            figsize=(VIZ_PARAMS['figure_width'], VIZ_PARAMS['figure_height'])
        )
        
        # Plot 1: Full waveform with beat markers
        ax1.plot(time, y, alpha=0.6, linewidth=0.5, color='blue', label='Waveform')
        ax1.set_xlabel('Time (seconds)', fontsize=12)
        ax1.set_ylabel('Amplitude', fontsize=12)
        ax1.set_title('Audio Waveform with Detected Metronome Beats', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        
        # Mark detected beats with vertical lines
        for beat_time in beat_times:
            ax1.axvline(x=beat_time, color='red', linestyle='--', linewidth=2, alpha=0.7)
        
        # Add legend
        legend_elements = [
            Line2D([0], [0], color='blue', linewidth=1, label='Audio Signal'),
            Line2D([0], [0], color='red', linestyle='--', linewidth=2, label='Detected Beats')
        ]
        ax1.legend(handles=legend_elements, loc='upper right')
        
        # Plot 2: Band-pass filtered signal (what the detector sees)
        sos = signal.butter(4, [800, 4000], 'bp', fs=sr, output='sos')
        y_filtered = signal.sosfilt(sos, y)
        
        ax2.plot(time, y_filtered, alpha=0.6, linewidth=0.5, color='green', label='Filtered (800-4000Hz)')
        ax2.set_xlabel('Time (seconds)', fontsize=12)
        ax2.set_ylabel('Amplitude', fontsize=12)
        ax2.set_title('Band-Pass Filtered Signal (What Metronome Detector Sees)', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        
        # Mark detected beats on filtered signal too
        for beat_time in beat_times:
            ax2.axvline(x=beat_time, color='red', linestyle='--', linewidth=2, alpha=0.7)
        
        ax2.legend(loc='upper right')
        
        plt.tight_layout()
        
        # Save the plot
        plot_filename = filepath.replace('.ogg', '_metronome_analysis.png')
        plt.savefig(plot_filename, dpi=VIZ_PARAMS['dpi'], bbox_inches='tight')
        plt.close()
        
        return {
            'success': True,
            'plot_path': plot_filename
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def visualize_pitch_and_notes(df, notes_df, beat_times, filepath):
    """Create comprehensive visualization with pitch, notes, and timing"""
    try:
        # Create figure with 3 subplots
        fig, (ax1, ax2, ax3) = plt.subplots(
            3, 1,
            figsize=(VIZ_PARAMS['figure_width'], VIZ_PARAMS['figure_height'] + 4)
        )
        
        # Plot 1: Pitch over time with note labels
        ax1.plot(df['time_s'], df['f0'], color='blue', linewidth=1, alpha=0.7, label='Detected Pitch')
        ax1.plot(df['time_s'], df['ideal_freq'], color='gray', linewidth=1, linestyle='--', alpha=0.5, label='Ideal Frequency')
        
        # Add metronome beats
        for beat_time in beat_times:
            ax1.axvline(x=beat_time, color='red', linestyle=':', linewidth=1, alpha=0.4)
        
        # Mark note onsets
        onset_times = df[df['is_onset']]['time_s'].values
        for onset_time in onset_times:
            ax1.axvline(x=onset_time, color='green', linestyle='-', linewidth=1.5, alpha=0.6)
        
        ax1.set_xlabel('Time (seconds)', fontsize=11)
        ax1.set_ylabel('Frequency (Hz)', fontsize=11)
        ax1.set_title('Pitch Tracking with Note Onsets and Metronome Beats', fontsize=13, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper right', fontsize=9)
        
        # Plot 2: Note segments with color coding by tuning
        ax2.set_xlabel('Time (seconds)', fontsize=11)
        ax2.set_ylabel('Note', fontsize=11)
        ax2.set_title('Detected Notes with Tuning Accuracy', fontsize=13, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='x')
        
        # Add metronome beats
        for beat_time in beat_times:
            ax2.axvline(x=beat_time, color='red', linestyle=':', linewidth=1, alpha=0.4)
        
        # Draw note segments as colored rectangles
        y_pos = 0
        unique_notes_list = notes_df['note_name'].unique()
        note_to_y = {note: i for i, note in enumerate(unique_notes_list)}
        
        for _, note in notes_df.iterrows():
            y_position = note_to_y[note['note_name']]
            
            # Color based on tuning accuracy
            abs_cents = abs(note['avg_cents_off'])
            if abs_cents <= 10:
                color = 'green'
                alpha = 0.7
            elif abs_cents <= 25:
                color = 'yellow'
                alpha = 0.7
            else:
                color = 'red'
                alpha = 0.7
            
            # Draw rectangle for note duration
            rect = Rectangle(
                (note['start_time'], y_position - 0.4),
                note['duration'],
                0.8,
                facecolor=color,
                alpha=alpha,
                edgecolor='black',
                linewidth=0.5
            )
            ax2.add_patch(rect)
            
            # Add note label
            if note['duration'] > 0.3:  # Only label if note is long enough
                ax2.text(
                    note['start_time'] + note['duration']/2,
                    y_position,
                    note['note_name'],
                    ha='center',
                    va='center',
                    fontsize=8,
                    fontweight='bold'
                )
        
        ax2.set_yticks(range(len(unique_notes_list)))
        ax2.set_yticklabels(unique_notes_list)
        ax2.set_ylim(-0.5, len(unique_notes_list) - 0.5)
        
        # Legend for tuning colors
        legend_elements = [
            Rectangle((0,0), 1, 1, facecolor='green', alpha=0.7, label='In tune (≤10¢)'),
            Rectangle((0,0), 1, 1, facecolor='yellow', alpha=0.7, label='Slightly off (≤25¢)'),
            Rectangle((0,0), 1, 1, facecolor='red', alpha=0.7, label='Out of tune (>25¢)'),
            Line2D([0], [0], color='red', linestyle=':', linewidth=1, label='Metronome')
        ]
        ax2.legend(handles=legend_elements, loc='upper right', fontsize=9)
        
        # Plot 3: Cents deviation over time
        ax3.plot(df['time_s'], df['cents_off'], color='purple', linewidth=1, alpha=0.7)
        ax3.axhline(y=0, color='black', linestyle='-', linewidth=1)
        ax3.axhline(y=10, color='green', linestyle='--', linewidth=0.8, alpha=0.5)
        ax3.axhline(y=-10, color='green', linestyle='--', linewidth=0.8, alpha=0.5)
        ax3.axhline(y=25, color='orange', linestyle='--', linewidth=0.8, alpha=0.5)
        ax3.axhline(y=-25, color='orange', linestyle='--', linewidth=0.8, alpha=0.5)
        
        # Add metronome beats
        for beat_time in beat_times:
            ax3.axvline(x=beat_time, color='red', linestyle=':', linewidth=1, alpha=0.4)
        
        ax3.set_xlabel('Time (seconds)', fontsize=11)
        ax3.set_ylabel('Cents Deviation', fontsize=11)
        ax3.set_title('Tuning Accuracy Over Time', fontsize=13, fontweight='bold')
        ax3.grid(True, alpha=0.3)
        ax3.set_ylim(-50, 50)
        
        plt.tight_layout()
        
        # Save the plot
        plot_filename = filepath.replace('.ogg', '_pitch_analysis.png')
        plt.savefig(plot_filename, dpi=VIZ_PARAMS['dpi'], bbox_inches='tight')
        plt.close()
        
        return {
            'success': True,
            'plot_path': plot_filename
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }