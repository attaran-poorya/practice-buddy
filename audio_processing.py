"""Audio processing functions for Practice Buddy Bot"""
import librosa
import numpy as np
from scipy import signal
from config import AUDIO_PARAMS, METRONOME_PARAMS


def load_audio(filepath):
    """Load audio file and extract basic properties"""
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
            'y': y,
            'sr': sr
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def detect_metronome(y, sr):
    """Detect metronome beeps/ticks and calculate tempo using periodicity"""
    try:
        # Band-pass filter for mechanical metronome
        sos = signal.butter(4, [800, 4000], 'bp', fs=sr, output='sos')
        y_filtered = signal.sosfilt(sos, y)
        
        # Get onset strength envelope
        onset_env = librosa.onset.onset_strength(
            y=y_filtered,
            sr=sr,
            hop_length=AUDIO_PARAMS['hop_length']
        )
        
        # Detect ALL potential onsets (lenient detection)
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=onset_env,
            sr=sr,
            hop_length=AUDIO_PARAMS['hop_length'],
            backtrack=False,
            pre_max=10,
            post_max=10,
            pre_avg=50,
            post_avg=50,
            delta=0.15,
            wait=int(0.3 * sr / AUDIO_PARAMS['hop_length']),
            units='frames'
        )
        
        # Convert frames to time
        onset_times = librosa.frames_to_time(
            onset_frames, 
            sr=sr, 
            hop_length=AUDIO_PARAMS['hop_length']
        )
        
        if len(onset_times) < 3:
            return {
                'success': True,
                'num_beats': len(onset_times),
                'tempo': 0,
                'beat_times': onset_times,
                'onset_env': onset_env
            }
        
        # Calculate intervals between all consecutive onsets
        intervals = np.diff(onset_times)
        
        # Find the dominant period using histogram clustering
        # Most intervals should cluster around the true metronome period
        hist, bin_edges = np.histogram(intervals, bins=50)
        dominant_bin = np.argmax(hist)
        dominant_interval = (bin_edges[dominant_bin] + bin_edges[dominant_bin + 1]) / 2
        
        # Calculate expected tempo
        tempo = 60.0 / dominant_interval if dominant_interval > 0 else 0
        
        # Now filter onsets to keep only those that fit the periodic pattern
        # Start with the first onset
        filtered_times = [onset_times[0]]
        expected_next = onset_times[0] + dominant_interval
        
        # Tolerance: allow ±15% deviation from expected interval
        tolerance = dominant_interval * 0.15
        
        for onset_time in onset_times[1:]:
            # Check if this onset is close to where we expect the next beat
            if abs(onset_time - expected_next) <= tolerance:
                filtered_times.append(onset_time)
                expected_next = onset_time + dominant_interval
            elif onset_time > expected_next + tolerance:
                # We might have missed a beat, reset expectation
                expected_next = onset_time + dominant_interval
                filtered_times.append(onset_time)
        
        filtered_times = np.array(filtered_times)
        
        # Recalculate tempo from filtered beats
        if len(filtered_times) > 1:
            intervals = np.diff(filtered_times)
            median_interval = np.median(intervals)
            tempo = 60.0 / median_interval if median_interval > 0 else 0
        
        return {
            'success': True,
            'num_beats': len(filtered_times),
            'tempo': tempo,
            'beat_times': filtered_times,
            'onset_env': onset_env,
            'all_onsets': onset_times  # Keep all onsets for debugging
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def extract_pitch(y, sr):
    """Extract fundamental frequency (f0) over time using YIN algorithm"""
    try:
        # Use YIN algorithm for pitch detection
        # hop_length from config (50ms resolution)
        hop_length = int(0.05 * sr)  # 50ms
        
        f0 = librosa.yin(
            y,
            fmin=AUDIO_PARAMS['fmin'],   # G3 (196 Hz)
            fmax=AUDIO_PARAMS['fmax'],   # A6 (1760 Hz)
            sr=sr,
            hop_length=hop_length
        )
        
        # Create time array for each frame
        times = librosa.frames_to_time(
            np.arange(len(f0)),
            sr=sr,
            hop_length=hop_length
        )
        
        # Handle NaN values (where pitch couldn't be detected)
        # Forward-fill NaNs for now
        f0_clean = f0.copy()
        nan_mask = np.isnan(f0_clean)
        
        # Interpolate NaNs
        if np.any(nan_mask):
            # Get indices of non-NaN values
            valid_indices = np.where(~nan_mask)[0]
            if len(valid_indices) > 0:
                # Interpolate
                f0_clean[nan_mask] = np.interp(
                    np.where(nan_mask)[0],
                    valid_indices,
                    f0_clean[valid_indices]
                )
        
        # Count how many frames had NaN
        nan_count = np.sum(nan_mask)
        nan_percentage = (nan_count / len(f0)) * 100
        
        # Create DataFrame
        import pandas as pd
        df = pd.DataFrame({
            'time_s': times,
            'f0': f0_clean,
            'f0_raw': f0  # Keep raw with NaNs for reference
        })
        
        return {
            'success': True,
            'df': df,
            'num_frames': len(f0),
            'nan_count': nan_count,
            'nan_percentage': nan_percentage,
            'frequency_range': (np.nanmin(f0), np.nanmax(f0))
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def identify_notes(df):
    """Convert frequencies to note names, MIDI numbers, and cents deviation"""
    try:
        import pandas as pd
        
        # Note names for mapping
        NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        
        # Convert frequency to MIDI number (continuous)
        # MIDI 69 = A4 = 440 Hz
        # Formula: midi = 69 + 12 * log2(f / 440)
        df['midi_float'] = 69 + 12 * np.log2(df['f0'] / 440.0)
        
        # Round to nearest MIDI integer
        df['midi_rounded'] = df['midi_float'].round().astype(int)
        
        # Calculate cents deviation from nearest note
        # 100 cents = 1 semitone
        df['cents_off'] = (df['midi_float'] - df['midi_rounded']) * 100
        
        # Map MIDI number to note name
        df['note_name'] = df['midi_rounded'].apply(
            lambda midi: NOTE_NAMES[midi % 12] + str(midi // 12 - 1)
        )
        
        # Calculate ideal frequency for the rounded MIDI note
        df['ideal_freq'] = 440.0 * (2 ** ((df['midi_rounded'] - 69) / 12))
        
        # Get note statistics
        note_counts = df['note_name'].value_counts().to_dict()
        unique_notes = df['note_name'].nunique()
        
        # Average cents deviation (absolute)
        avg_cents_off = df['cents_off'].abs().mean()
        
        return {
            'success': True,
            'df': df,
            'note_counts': note_counts,
            'unique_notes': unique_notes,
            'avg_cents_off': avg_cents_off
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def segment_notes(df, y, sr):
    """Segment continuous pitch data into discrete note events"""
    try:
        import pandas as pd
        
        # Detect note onsets using librosa
        hop_length = int(0.05 * sr)
        onset_frames = librosa.onset.onset_detect(
            y=y,
            sr=sr,
            hop_length=hop_length,
            backtrack=False,
            pre_max=20,
            post_max=20,
            pre_avg=100,
            post_avg=100,
            delta=0.07,  # Lower threshold to catch more violin onsets
            wait=int(0.1 * sr / hop_length),  # Min 0.1s between onsets
            units='frames'
        )
        
        onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop_length)
        
        # Add onset markers to DataFrame
        df['is_onset'] = False
        for onset_time in onset_times:
            # Find closest frame to this onset
            closest_idx = (df['time_s'] - onset_time).abs().idxmin()
            df.loc[closest_idx, 'is_onset'] = True
        
        # Hybrid approach: combine onsets with pitch change detection
        # Detect significant MIDI changes (> 1 semitone)
        df['midi_change'] = df['midi_rounded'].diff().abs()
        df['is_pitch_change'] = df['midi_change'] > 1
        
        # Combine: onset OR significant pitch change
        df['is_note_start'] = df['is_onset'] | df['is_pitch_change']
        
        # Segment notes based on note starts
        notes = []
        current_note_start = 0
        
        for i in range(1, len(df)):
            if df.loc[i, 'is_note_start']:
                # End previous note
                if i > current_note_start:
                    note_segment = df.loc[current_note_start:i-1]
                    
                    if len(note_segment) > 0:
                        notes.append({
                            'start_time': note_segment['time_s'].iloc[0],
                            'end_time': note_segment['time_s'].iloc[-1],
                            'duration': note_segment['time_s'].iloc[-1] - note_segment['time_s'].iloc[0],
                            'note_name': note_segment['note_name'].mode()[0] if len(note_segment['note_name'].mode()) > 0 else note_segment['note_name'].iloc[0],
                            'midi_number': int(note_segment['midi_rounded'].median()),
                            'avg_frequency': note_segment['f0'].mean(),
                            'ideal_frequency': note_segment['ideal_freq'].mean(),
                            'avg_cents_off': note_segment['cents_off'].mean(),
                            'abs_avg_cents_off': note_segment['cents_off'].abs().mean()
                        })
                
                current_note_start = i
        
        # Add final note
        if current_note_start < len(df):
            note_segment = df.loc[current_note_start:]
            if len(note_segment) > 0:
                notes.append({
                    'start_time': note_segment['time_s'].iloc[0],
                    'end_time': note_segment['time_s'].iloc[-1],
                    'duration': note_segment['time_s'].iloc[-1] - note_segment['time_s'].iloc[0],
                    'note_name': note_segment['note_name'].mode()[0] if len(note_segment['note_name'].mode()) > 0 else note_segment['note_name'].iloc[0],
                    'midi_number': int(note_segment['midi_rounded'].median()),
                    'avg_frequency': note_segment['f0'].mean(),
                    'ideal_frequency': note_segment['ideal_freq'].mean(),
                    'avg_cents_off': note_segment['cents_off'].mean(),
                    'abs_avg_cents_off': note_segment['cents_off'].abs().mean()
                })
        
        notes_df = pd.DataFrame(notes)
        
        return {
            'success': True,
            'df': df,  # Return updated DataFrame with onset markers
            'notes': notes_df,
            'num_notes': len(notes_df),
            'num_onsets': len(onset_times),
            'onset_times': onset_times
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }