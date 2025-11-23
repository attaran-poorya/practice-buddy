"""Video generation functions for Practice Buddy Bot"""
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from config import VIZ_PARAMS


def create_video_frame(df, notes_df, current_time, audio_duration):
    """Create a single frame for the video at a specific timestamp"""
    try:
        fig, (ax1, ax2, ax3) = plt.subplots(
            3, 1,
            figsize=(12, 10),
            dpi=80
        )
        
        # Define window size (show 10 seconds of data at a time)
        window_size = 10
        time_start = max(0, current_time - window_size / 2)
        time_end = min(audio_duration, current_time + window_size / 2)
        
        # Filter data for current window
        mask = (df['time_s'] >= time_start) & (df['time_s'] <= time_end)
        df_window = df[mask]
        
        # Plot 1: Pitch tracking
        if len(df_window) > 0:
            ax1.plot(df_window['time_s'], df_window['f0'], color='blue', linewidth=2, alpha=0.7, label='Detected')
            ax1.plot(df_window['time_s'], df_window['ideal_freq'], color='gray', linewidth=1, linestyle='--', alpha=0.5, label='Ideal')
        
        # Current time marker
        ax1.axvline(x=current_time, color='red', linestyle='-', linewidth=3, alpha=0.8)
        ax1.set_xlim(time_start, time_end)
        ax1.set_xlabel('Time (seconds)', fontsize=11)
        ax1.set_ylabel('Frequency (Hz)', fontsize=11)
        ax1.set_title(f'Pitch - Time: {current_time:.1f}s / {audio_duration:.1f}s', fontsize=13, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper right', fontsize=9)
        
        # Plot 2: Note segments
        ax2.set_xlabel('Time (seconds)', fontsize=11)
        ax2.set_ylabel('Note', fontsize=11)
        ax2.set_title('Notes (Green=In Tune, Yellow=Slightly Off, Red=Out of Tune)', fontsize=13, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='x')
        
        # Filter notes in current window
        notes_window = notes_df[
            ((notes_df['start_time'] >= time_start) & (notes_df['start_time'] <= time_end)) |
            ((notes_df['end_time'] >= time_start) & (notes_df['end_time'] <= time_end)) |
            ((notes_df['start_time'] <= time_start) & (notes_df['end_time'] >= time_end))
        ]
        
        if len(notes_window) > 0:
            unique_notes = notes_window['note_name'].unique()
            note_to_y = {note: i for i, note in enumerate(unique_notes)}
            
            for _, note in notes_window.iterrows():
                y_position = note_to_y[note['note_name']]
                abs_cents = abs(note['avg_cents_off'])
                
                # Color based on tuning
                if abs_cents <= 10:
                    color = 'green'
                elif abs_cents <= 25:
                    color = 'yellow'
                else:
                    color = 'red'
                
                # Highlight current note being played
                is_current = note['start_time'] <= current_time <= note['end_time']
                alpha = 0.95 if is_current else 0.6
                linewidth = 3 if is_current else 0.5
                
                rect = Rectangle(
                    (note['start_time'], y_position - 0.4),
                    note['duration'],
                    0.8,
                    facecolor=color,
                    alpha=alpha,
                    edgecolor='black',
                    linewidth=linewidth
                )
                ax2.add_patch(rect)
                
                # Add note label
                if note['duration'] > 0.3:
                    ax2.text(
                        note['start_time'] + note['duration']/2,
                        y_position,
                        note['note_name'],
                        ha='center',
                        va='center',
                        fontsize=9,
                        fontweight='bold'
                    )
            
            ax2.set_yticks(range(len(unique_notes)))
            ax2.set_yticklabels(unique_notes)
            ax2.set_ylim(-0.5, len(unique_notes) - 0.5)
        
        # Current time marker
        ax2.axvline(x=current_time, color='red', linestyle='-', linewidth=3, alpha=0.8)
        ax2.set_xlim(time_start, time_end)
        
        # Plot 3: Cents deviation
        if len(df_window) > 0:
            ax3.plot(df_window['time_s'], df_window['cents_off'], color='purple', linewidth=2, alpha=0.7)
        
        ax3.axhline(y=0, color='black', linestyle='-', linewidth=1.5)
        ax3.axhline(y=10, color='green', linestyle='--', linewidth=1, alpha=0.5)
        ax3.axhline(y=-10, color='green', linestyle='--', linewidth=1, alpha=0.5)
        ax3.axhline(y=25, color='orange', linestyle='--', linewidth=1, alpha=0.5)
        ax3.axhline(y=-25, color='orange', linestyle='--', linewidth=1, alpha=0.5)
        ax3.axvline(x=current_time, color='red', linestyle='-', linewidth=3, alpha=0.8)
        
        ax3.set_xlim(time_start, time_end)
        ax3.set_ylim(-50, 50)
        ax3.set_xlabel('Time (seconds)', fontsize=11)
        ax3.set_ylabel('Cents Deviation', fontsize=11)
        ax3.set_title('Tuning Accuracy (0 = Perfect Pitch)', fontsize=13, fontweight='bold')
        ax3.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Convert figure to numpy array (FIX: use tobytes instead of tostring_rgb)
        fig.canvas.draw()
        buf = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
        w, h = fig.canvas.get_width_height()
        img = buf.reshape((h, w, 4))  # RGBA format
        img = img[:, :, :3]  # Convert to RGB by dropping alpha channel
        
        plt.close(fig)
        
        return img
        
    except Exception as e:
        print(f"Error creating frame at {current_time}s: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_video_report(df, notes_df, beat_times, audio_path, output_path):
    """Generate synchronized video report with audio"""
    try:
        from moviepy.editor import VideoClip, AudioFileClip
        import librosa
        
        print("Starting video generation...")
        
        # Load audio duration
        audio_duration = librosa.get_duration(path=audio_path)
        print(f"Audio duration: {audio_duration:.2f}s")
        
        # Test create first frame to catch errors early
        print("Creating test frame...")
        test_frame = create_video_frame(df, notes_df, 0, audio_duration)
        if test_frame is None:
            raise Exception("Failed to create test frame - check error messages above")
        
        print(f"✓ Test frame OK: {test_frame.shape}")
        
        # Create video clip
        frame_count = [0]  # Use list to modify in closure
        
        def make_frame(t):
            frame_count[0] += 1
            if frame_count[0] % 10 == 0:  # Progress update every 10 frames
                print(f"  Rendering frame {frame_count[0]} (t={t:.1f}s)...")
            
            frame = create_video_frame(df, notes_df, t, audio_duration)
            if frame is None:
                print(f"Warning: Failed to create frame at t={t:.2f}s, using fallback")
                return test_frame
            return frame
        
        print("Creating video clip (this will take a minute)...")
        video = VideoClip(make_frame, duration=audio_duration)
        video = video.set_fps(10)
        
        print("Loading audio...")
        audio = AudioFileClip(audio_path)
        final_video = video.set_audio(audio)
        
        print(f"Writing video to {output_path}...")
        final_video.write_videofile(
            output_path,
            fps=10,
            codec='libx264',
            audio_codec='aac',
            bitrate='2000k',
            preset='ultrafast',  # Faster encoding
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            verbose=False,
            logger=None
        )
        
        print("✓ Video generation complete!")
        
        # Clean up
        video.close()
        audio.close()
        final_video.close()
        
        return {
            'success': True,
            'video_path': output_path,
            'duration': audio_duration
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Video generation error:\n{error_details}")
        return {
            'success': False,
            'error': str(e)
        }