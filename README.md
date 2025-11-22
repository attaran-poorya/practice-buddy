# Practice Buddy Bot

A Telegram bot that analyzes violin practice recordings with metronome, providing pitch accuracy feedback and timing analysis.

## Features

- 🎵 **Metronome Detection**: Automatically detects metronome beats using periodicity-based algorithm
- 🎼 **Pitch Tracking**: Extracts fundamental frequency using YIN algorithm
- 🎹 **Note Identification**: Converts frequencies to note names with MIDI numbers
- 📊 **Tuning Analysis**: Calculates cents deviation from ideal pitch
- 🎯 **Note Segmentation**: Identifies discrete note events with onset detection
- 📈 **Visual Reports**: Generates comprehensive analysis visualizations

## Current Version

**v0.1.0** - Initial development version
- Basic metronome detection with periodicity filtering
- Pitch tracking and note identification
- Note segmentation with hybrid onset detection
- Multi-panel visualization with tuning color coding

## Installation

### Local Development

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd practicebuddy-bot
```

2. **Create virtual environment**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
Create a `.env` file in the project root:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

5. **Run the bot**
```bash
python bot.py
```

### Server Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for instructions on deploying to a server.

## Project Structure

```
practicebuddy-bot/
├── bot.py                  # Main bot logic and Telegram handlers
├── audio_processing.py     # Audio analysis functions
├── visualization.py        # Plotting and visualization
├── config.py              # Configuration and parameters
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (not in git)
├── .gitignore            # Git ignore rules
├── README.md             # This file
└── voice_messages/       # Audio files storage (not in git)
```

## Usage

1. Start a conversation with your bot on Telegram
2. Send a voice message of your violin practice with metronome
3. The bot will analyze and return:
   - Audio properties
   - Metronome detection results with visualization
   - Pitch analysis
   - Note identification
   - Comprehensive pitch analysis visualization

## Configuration

Edit `config.py` to adjust:
- Audio processing parameters (frequency range, hop length)
- Metronome detection sensitivity
- Visualization settings

## Development Roadmap

- [ ] Video report generation (Iteration 8-10)
- [ ] Sheet music alignment
- [ ] Practice session history tracking
- [ ] Multi-user support with practice statistics
- [ ] Web dashboard for analysis review

## Known Issues

- Metronome detection may need tuning for different metronome types
- Pitch tracking can struggle with vibrato and fast passages
- Currently optimized for one test file (needs more validation)

## Contributing

This is currently in active early development. Feedback welcome!

## License

[To be determined]