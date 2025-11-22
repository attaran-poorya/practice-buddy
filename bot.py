"""Main bot file for Practice Buddy Bot"""
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from config import BOT_TOKEN, VOICE_FOLDER
from audio_processing import load_audio, detect_metronome, extract_pitch, identify_notes, segment_notes
from visualization import visualize_metronome_detection, visualize_pitch_and_notes

# Create voice_messages folder if it doesn't exist
os.makedirs(VOICE_FOLDER, exist_ok=True)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming voice messages"""
    voice = update.message.voice
    
    # Get the file
    file = await context.bot.get_file(voice.file_id)
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"voice_{timestamp}.ogg"
    filepath = os.path.join(VOICE_FOLDER, filename)
    
    # Download the file
    await file.download_to_drive(filepath)
    
    # Send initial confirmation
    await update.message.reply_text(
        f"✅ Voice message saved as: {filename}\n🎵 Analyzing audio..."
    )
    print(f"Downloaded: {filename}")
    
    # Load and analyze audio
    result = load_audio(filepath)
    
    if not result['success']:
        await update.message.reply_text(f"❌ Error analyzing audio: {result['error']}")
        print(f"Error: {result['error']}")
        return
    
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
    
    if not metronome_result['success']:
        await update.message.reply_text(
            f"❌ Error detecting metronome: {metronome_result['error']}"
        )
        print(f"Metronome error: {metronome_result['error']}")
        return
    
    # Send metronome results
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
    
    if not viz_result['success']:
        await update.message.reply_text(
            f"❌ Error creating visualization: {viz_result['error']}"
        )
        print(f"Visualization error: {viz_result['error']}")
        return
    
    # Send the plot image
    with open(viz_result['plot_path'], 'rb') as photo:
        await update.message.reply_photo(
            photo=photo,
            caption="Waveform with detected metronome beats highlighted in red"
        )
    print(f"Visualization sent: {viz_result['plot_path']}")
    
    # Iteration 3: Extract pitch
    await update.message.reply_text("🎼 Extracting pitch information...")
    pitch_result = extract_pitch(result['y'], result['sr'])
    
    if not pitch_result['success']:
        await update.message.reply_text(
            f"❌ Error extracting pitch: {pitch_result['error']}"
        )
        print(f"Pitch error: {pitch_result['error']}")
        return
    
    # Send pitch analysis results
    freq_min, freq_max = pitch_result['frequency_range']
    message = (
        f"🎵 Pitch Analysis:\n"
        f"Analyzed {pitch_result['num_frames']} frames\n"
        f"Frequency range: {freq_min:.1f} - {freq_max:.1f} Hz\n"
        f"NaN frames: {pitch_result['nan_count']} ({pitch_result['nan_percentage']:.1f}%)\n"
        f"✅ Pitch tracking complete!"
    )
    await update.message.reply_text(message)
    print(f"Pitch: {pitch_result['num_frames']} frames, {freq_min:.1f}-{freq_max:.1f} Hz")
    
    # Iteration 4: Identify notes
    await update.message.reply_text("🎼 Identifying notes...")
    note_result = identify_notes(pitch_result['df'])
    
    if not note_result['success']:
        await update.message.reply_text(
            f"❌ Error identifying notes: {note_result['error']}"
        )
        print(f"Note identification error: {note_result['error']}")
        return
    
    # Get top 5 most common notes
    top_notes = sorted(
        note_result['note_counts'].items(), 
        key=lambda x: x[1], 
        reverse=True
    )[:5]
    top_notes_str = ", ".join([f"{note} ({count}x)" for note, count in top_notes])
    
    # Send note identification results
    message = (
        f"🎹 Note Identification:\n"
        f"Detected {note_result['unique_notes']} unique notes\n"
        f"Top notes: {top_notes_str}\n"
        f"Average tuning deviation: {note_result['avg_cents_off']:.1f} cents\n"
        f"✅ Note identification complete!"
    )
    await update.message.reply_text(message)
    print(f"Notes: {note_result['unique_notes']} unique, avg deviation {note_result['avg_cents_off']:.1f} cents")
    
    # Iterations 5-7 Combined: Segment notes and create comprehensive visualization
    await update.message.reply_text("🎼 Segmenting notes and creating visualization...")
    segment_result = segment_notes(note_result['df'], result['y'], result['sr'])
    
    if not segment_result['success']:
        await update.message.reply_text(
            f"❌ Error segmenting notes: {segment_result['error']}"
        )
        print(f"Note segmentation error: {segment_result['error']}")
        return
    
    # Send segmentation results
    message = (
        f"🎵 Note Segmentation:\n"
        f"Detected {segment_result['num_onsets']} note onsets\n"
        f"Identified {segment_result['num_notes']} distinct note events\n"
        f"✅ Segmentation complete!"
    )
    await update.message.reply_text(message)
    print(f"Segmentation: {segment_result['num_notes']} notes from {segment_result['num_onsets']} onsets")
    
    # Create comprehensive pitch visualization
    await update.message.reply_text("📊 Generating pitch analysis visualization...")
    viz_result = visualize_pitch_and_notes(
        segment_result['df'],
        segment_result['notes'],
        metronome_result['beat_times'],
        filepath
    )
    
    if not viz_result['success']:
        await update.message.reply_text(
            f"❌ Error creating pitch visualization: {viz_result['error']}"
        )
        print(f"Pitch visualization error: {viz_result['error']}")
        return
    
    # Send the pitch analysis visualization
    with open(viz_result['plot_path'], 'rb') as photo:
        await update.message.reply_photo(
            photo=photo,
            caption="Comprehensive pitch analysis: frequency tracking, detected notes with tuning accuracy, and timing"
        )
    print(f"Pitch visualization sent: {viz_result['plot_path']}")


def main():
    """Start the bot"""
    # Create the Application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handler for voice messages
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    print("🤖 Practice Buddy Bot is running... Press Ctrl+C to stop")
    
    # Start the bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()