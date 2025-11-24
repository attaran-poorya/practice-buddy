"""Video generation functions for Practice Buddy Bot"""
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from config import VIZ_PARAMS


def create_video_frame(df, notes_df, current_time, audio_duration):
    """Create a single frame - simplified with progressive line drawing"""
    try:
        fig, (ax1, ax2) = plt.subplots(
            2, 1,
            figsize=(12, 8),
            dpi=60  # Lower DPI for faster rendering
        )
        
        # Filter data up to current time
        mask = df['time_s'] <= current_time
        df_current = df[mask]
        
        # Plot 1: Pitch tracking (draw full axes, progressive line)
        ax1.set_xlim(0, audio_duration)
        ax1.set_ylim(df['f0'].min() * 0.95, df['f0'].max() * 1.05)
        ax1.set_xlabel('Time (seconds)', fontsize=11)
        ax1.set_ylabel('Frequency (Hz)', fontsize=11)
        ax1.set_title(f'Pitch - {current_time:.1f}s / {audio_duration:.1f}s', fontsize=13, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        
        # Draw pitch line up to current time only
        if len(df_current) > 0:
            ax1.plot(df_current['time_s'], df_current['f0'], color='blue', linewidth=2)
            ax1.plot(df_current['time_s'], df_current['ideal_freq'], color='gray', linewidth=1, linestyle='--', alpha=0.5)
        
        # Current position marker
        ax1.axvline(x=current_time, color='red', linestyle='-', linewidth=2, alpha=0.8)
        
        # Plot 2: Cents deviation (draw full axes, progressive line)
        ax2.set_xlim(0, audio_duration)
        ax2.set_ylim(-50, 50)
        ax2.set_xlabel('Time (seconds)', fontsize=11)
        ax2.set_ylabel('Cents Deviation', fontsize=11)
        ax2.set_title('Tuning Accuracy', fontsize=13, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        
        # Reference lines (static, full width)
        ax2.axhline(y=0, color='black', linestyle='-', linewidth=1.5)
        ax2.axhline(y=10, color='green', linestyle='--', linewidth=1, alpha=0.5)
        ax2.axhline(y=-10, color='green', linestyle='--', linewidth=1, alpha=0.5)
        ax2.axhline(y=25, color='orange', linestyle='--', linewidth=1, alpha=0.5)
        ax2.axhline(y=-25, color='orange', linestyle='--', linewidth=1, alpha=0.5)
        
        # Draw cents line up to current time only
        if len(df_current) > 0:
            ax2.plot(df_current['time_s'], df_current['cents_off'], color='purple', linewidth=2)
        
        # Current position marker
        ax2.axvline(x=current_time, color='red', linestyle='-', linewidth=2, alpha=0.8)
        
        plt.tight_layout()
        
        # Convert to image
        fig.canvas.draw()
        buf = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
        w, h = fig.canvas.get_width_height()
        img = buf.reshape((h, w, 4))[:, :, :3]  # Drop alpha
        
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
        import signal as sig
        
        # Timeout handler
        def timeout_handler(signum, frame):
            raise TimeoutError("Video generation timeout (5 minutes)")
        
        # Set 5 minute timeout
        sig.signal(sig.SIGALRM, timeout_handler)
        sig.alarm(300)  # 5 minutes
        
        print("Starting video generation...")
        
        # Load audio duration
        audio_duration = librosa.get_duration(path=audio_path)
        print(f"Audio duration: {audio_duration:.2f}s")
        
        # Limit video generation to max 2 minutes of audio
        if audio_duration > 120:
            print(f"Warning: Audio is {audio_duration:.1f}s, truncating video to 120s")
            audio_duration = 120
        
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
        audio = audio.subclip(0, audio_duration)  # Match video duration
        final_video = video.set_audio(audio)
        
        print(f"Writing video to {output_path}...")
        final_video.write_videofile(
            output_path,
            fps=10,
            codec='libx264',
            audio_codec='aac',
            bitrate='1500k',  # Reduced from 2000k for smaller file
            preset='faster',  # Balance between speed and compression
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            verbose=False,
            logger=None,
            threads=2  # Limit threads to avoid memory issues
        )
        
        # Cancel alarm
        sig.alarm(0)
        
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
        
    except TimeoutError as e:
        print(f"❌ Video generation timed out: {e}")
        return {
            'success': False,
            'error': 'Video generation timeout (>5 minutes). Try with shorter recordings (<60s).'
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Video generation error:\n{error_details}")
        return {
            'success': False,
            'error': str(e)
        }