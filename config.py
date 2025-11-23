"""Configuration settings for Practice Buddy Bot"""
import os
from dotenv import load_dotenv

# Version
VERSION = "0.1.0"

# Load environment variables
load_dotenv()

# Bot settings
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Folder settings
VOICE_FOLDER = "voice_messages"

# Audio processing parameters
AUDIO_PARAMS = {
    'hop_length': 512,
    'fmin': 196,  # G3
    'fmax': 1760,  # A6
}

# Metronome detection parameters
METRONOME_PARAMS = {
    'highpass_freq': 2000,  # Hz
    'pre_max': 20,
    'post_max': 20,
    'pre_avg': 100,
    'post_avg': 100,
    'delta': 0.3,
    'min_interval': 0.4,  # seconds (150 BPM max)
}

# Visualization settings
VIZ_PARAMS = {
    'figure_width': 14,
    'figure_height': 8,
    'dpi': 150,
}