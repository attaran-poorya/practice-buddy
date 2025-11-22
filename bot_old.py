import os
import librosa
import numpy as np
from scipy import signal as sig
import matplotlib.pyplot as plt
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Create voice_messages folder if it doesn't exist
VOICE_FOLDER = "voice_messages"
os.makedirs(VOICE_FOLDER, exist_ok=True)

def visualize_metronome_detection(y, sr, beat_times, filepath):
    """Create visualization of waveform with detected beats highlighted"""
    try:
        # Create time array for x-axis
        duration = len(y) / sr
        time = np.linspace(0, duration, len(y))
        
        # Create figure with 2 subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8))
        
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
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], color='blue', linewidth=1, label='Audio Signal'),
            Line2D([0], [0], color='red', linestyle='--', linewidth=2, label='Detected Beats')
        ]
        ax1.legend(handles=legend_elements, loc='upper right')
        
        # Plot 2: High-pass filtered signal (what the detector sees)
        from scipy import signal as sig
        sos = sig.butter(4, 2000, 'hp', fs=sr, output='sos')
        y_filtered = sig.sosfilt(sos, y)
        
        ax2.plot(time, y_filtered, alpha=0.6, linewidth=0.5, color='green', label='Filtered (>2000Hz)')
        ax2.set_xlabel('Time (seconds)', fontsize=12)
        ax2.set_ylabel('Amplitude', fontsize=12)
        ax2.set_title('High-Pass Filtered Signal (What Metronome Detector Sees)', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        
        # Mark detected beats on filtered signal too
        for beat_time in beat_times:
            ax2.axvline(x=beat_time, color='red', linestyle='--', linewidth=2, alpha=0.7)
        
        ax2.legend(loc='upper right')
        
        plt.tight_layout()
        
        # Save the plot
        plot_filename = filepath.replace('.ogg', '_metronome_analysis.png')
        plt.savefig(plot_filename, dpi=150, bbox_inches='tight')
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

def detect_metronome(y, sr):
    """Detect metronome beeps/ticks and calculate tempo"""
    try:
        # High-pass filter to isolate metronome clicks (typically > 2000 Hz)
        # Mechanical metronome ticks are sharp, high-frequency transients
        sos = sig.butter(4, 2000, 'hp', fs=sr, output='sos')
        y_filtered = sig.sosfilt(sos, y)
        
        # Detect onsets with stricter parameters for sharp transients
        onset_frames = librosa.onset.onset_detect(
            y=y_filtered, 
            sr=sr,
            hop_length=512,
            backtrack=False,
            pre_max=20,      # Increase pre_max to be more selective
            post_max=20,     # Increase post_max to be more selective
            pre_avg=100,     # Increase pre_avg for better peak detection
            post_avg=100,    # Increase post_avg for better peak detection
            delta=0.3,       # Increase threshold for onset strength
            wait=int(0.3 * sr / 512),  # Minimum 0.3s between beats (200 BPM max)
            units='frames'
        )
        
        # Convert frames to time
        onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=512)
        
        # Additional filtering: remove beats too close together
        # For 60 BPM, beats should be ~1 second apart
        min_interval = 0.4  # Minimum 0.4s between beats (150 BPM max)
        filtered_times = []
        if len(onset_times) > 0:
            filtered_times.append(onset_times[0])
            for t in onset_times[1:]:
                if t - filtered_times[-1] >= min_interval:
                    filtered_times.append(t)
        
        filtered_times = np.array(filtered_times)
        
        # Calculate tempo from onset intervals
        if len(filtered_times) > 1:
            intervals = np.diff(filtered_times)
            median_interval = np.median(intervals)
            tempo = 60.0 / median_interval if median_interval > 0 else 0
        else:
            tempo = 0
        
        return {
            'success': True,
            'num_beats': len(filtered_times),
            'tempo': tempo,
            'beat_times': filtered_times
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
    """Detect metronome beeps/ticks and calculate tempo"""
    try:
        # High-pass filter to isolate metronome clicks (typically > 2000 Hz)
        # Mechanical metronome ticks are sharp, high-frequency transients
        from scipy import signal as sig
        sos = sig.butter(4, 2000, 'hp', fs=sr, output='sos')
        y_filtered = sig.sosfilt(sos, y)
        
        # Detect onsets with stricter parameters for sharp transients
        onset_frames = librosa.onset.onset_detect(
            y=y_filtered, 
            sr=sr,
            hop_length=512,
            backtrack=False,
            pre_max=20,      # Increase pre_max to be more selective
            post_max=20,     # Increase post_max to be more selective
            pre_avg=100,     # Increase pre_avg for better peak detection
            post_avg=100,    # Increase post_avg for better peak detection
            delta=0.3,       # Increase threshold for onset strength
            wait=int(0.3 * sr / 512),  # Minimum 0.3s between beats (200 BPM max)
            units='frames'
        )
        
        # Convert frames to time
        onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=512)
        
        # Additional filtering: remove beats too close together
        # For 60 BPM, beats should be ~1 second apart
        min_interval = 0.4  # Minimum 0.4s between beats (150 BPM max)
        filtered_times = []
        if len(onset_times) > 0:
            filtered_times.append(onset_times[0])
            for t in onset_times[1:]:
                if t - filtered_times[-1] >= min_interval:
                    filtered_times.append(t)
        
        filtered_times = np.array(filtered_times)
        
        # Calculate tempo from onset intervals
        if len(filtered_times) > 1:
            intervals = np.diff(filtered_times)
            median_interval = np.median(intervals)
            tempo = 60.0 / median_interval if median_interval > 0 else 0
        else:
            tempo = 0
        
        return {
            'success': True,
            'num_beats': len(filtered_times),
            'tempo': tempo,
            'beat_times': filtered_times
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def analyze_audio(filepath):
    """Load audio and extract basic properties"""
    try:
        # Load audio file
        y, sr = librosa.load(filepath, sr=None)
        
        # Calculate duration
        duration = librosa.get_duration(y=y, sr=sr)
        
        # Get audio shape info
        num_samples = len(y)
        
        return {
            'success': True,
            'duration': duration,
            'sample_rate': sr,
            'num_samples': num_samples,
            'audio_shape': y.shape,
            'y': y,  # Return audio data for further processing
            'sr': sr
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming voice messages"""
    voice = update.message.voice
    
    # Get the file
    file = await context.bot.get_file(voice.file_id)
    
    # Create filename with timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"voice_{timestamp}.ogg"
    filepath = os.path.join(VOICE_FOLDER, filename)
    
    # Download the file
    await file.download_to_drive(filepath)
    
    # Send initial confirmation
    await update.message.reply_text(f"✅ Voice message saved as: {filename}\n🎵 Analyzing audio...")
    print(f"Downloaded: {filename}")
    
    # Analyze the audio
    result = analyze_audio(filepath)
    
    if result['success']:
        # Send basic analysis results
        message = (
            f"📊 Audio Analysis:\n"
            f"Duration: {result['duration']:.2f} seconds\n"
            f"Sample Rate: {result['sample_rate']} Hz\n"
            f"Total Samples: {result['num_samples']:,}\n"
            f"✅ Audio loaded successfully!"
        )
        await update.message.reply_text(message)
        print(f"Analysis complete: {result['duration']:.2f}s at {result['sample_rate']}Hz")
        
        # Detect metronome
        await update.message.reply_text("🎯 Detecting metronome...")
        metronome_result = detect_metronome(result['y'], result['sr'])
        
        if metronome_result['success']:
            message = (
                f"🎼 Metronome Detection:\n"
                f"Detected {metronome_result['num_beats']} beats\n"
                f"Estimated Tempo: {metronome_result['tempo']:.1f} BPM\n"
                f"✅ Metronome analysis complete!"
            )
            await update.message.reply_text(message)
            print(f"Metronome: {metronome_result['num_beats']} beats at {metronome_result['tempo']:.1f} BPM")
            
            # Create visualization
            await update.message.reply_text("📊 Generating visualization...")
            viz_result = visualize_metronome_detection(
                result['y'], 
                result['sr'], 
                metronome_result['beat_times'],
                filepath
            )
            
            if viz_result['success']:
                # Send the plot image
                with open(viz_result['plot_path'], 'rb') as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption="Waveform with detected metronome beats highlighted in red"
                    )
                print(f"Visualization sent: {viz_result['plot_path']}")
            else:
                await update.message.reply_text(f"❌ Error creating visualization: {viz_result['error']}")
                print(f"Visualization error: {viz_result['error']}")
        else:
            await update.message.reply_text(f"❌ Error detecting metronome: {metronome_result['error']}")
            print(f"Metronome error: {metronome_result['error']}")
    else:
        await update.message.reply_text(f"❌ Error analyzing audio: {result['error']}")
        print(f"Error: {result['error']}")

def main():
    """Start the bot"""
    # Create the Application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handler for voice messages
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    print("Bot is running... Press Ctrl+C to stop")
    
    # Start the bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()