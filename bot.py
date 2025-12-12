"""Main bot file for Practice Buddy Bot"""
import os
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler,
    MessageHandler, 
    CallbackQueryHandler,
    ConversationHandler,
    filters, 
    ContextTypes
)

from config import BOT_TOKEN, VOICE_FOLDER, VERSION
from audio_processing import load_audio, detect_metronome, extract_pitch, identify_notes, segment_notes, calculate_timing_accuracy
from visualization import visualize_metronome_detection, visualize_pitch_and_notes
from video_generation import generate_video_report
import messages as msg
from conversation import (
    State,
    start_command,
    help_command,
    cancel_command,
    button_callback,
    ask_instrument,
    receive_piece_name,
    receive_audio,
    invalid_input
)

# Create voice_messages folder if it doesn't exist
os.makedirs(VOICE_FOLDER, exist_ok=True)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming voice messages with analysis"""
    voice = update.message.voice
    
    # Skip if we're in conversation mode (it will be handled by conversation handler)
    if context.user_data.get('in_conversation'):
        context.user_data.pop('in_conversation')  # Clear flag
        # Now proceed with analysis
    
    # Get context from conversation if available
    analysis_context = context.user_data.get('analysis_context', {})
    instrument = analysis_context.get('instrument', 'نامشخص')
    piece_name = analysis_context.get('piece_name', 'نامشخص')
    
    print(f"=== STARTING ANALYSIS ===")
    print(f"Instrument: {instrument}, Piece: {piece_name}")
    
    # Get the file
    file = await context.bot.get_file(voice.file_id)
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"voice_{timestamp}.ogg"
    filepath = os.path.join(VOICE_FOLDER, filename)
    
    # Download the file
    print(f"Downloading file to {filepath}...")
    await file.download_to_drive(filepath)
    print(f"✓ Downloaded: {filename}")
    
    # Send "file received" message
    await update.message.reply_text(msg.FILE_RECEIVED)
    
    # Load and analyze audio
    print("Loading audio...")
    await update.message.reply_text(msg.ANALYZING_AUDIO)
    result = load_audio(filepath)
    print(f"Audio loaded: {result.get('success')}")
    
    if not result['success']:
        print(f"ERROR: Audio load failed - {result['error']}")
        await update.message.reply_text(f"❌ {msg.ERROR_ANALYSIS_FAILED}\n{result['error']}")
        return
    
    print(f"✓ Audio: {result['duration']:.2f}s, {result['sample_rate']}Hz")
    
    # Send basic analysis results
    message = (
        f"📊 تحلیل صوتی\n"
        f"مدت: {result['duration']:.2f} ثانیه\n"
        f"نرخ نمونه‌برداری: {result['sample_rate']} Hz\n"
        f"✅ فایل صوتی بارگذاری شد"
    )
    await update.message.reply_text(message)
    
    # Detect metronome
    print("Detecting metronome...")
    await update.message.reply_text(msg.DETECTING_METRONOME)
    metronome_result = detect_metronome(result['y'], result['sr'])
    print(f"Metronome detected: {metronome_result.get('success')}")
    
    if not metronome_result['success']:
        await update.message.reply_text(f"❌ خطا در تشخیص مترونوم: {metronome_result['error']}")
        print(f"Metronome error: {metronome_result['error']}")
        return
    
    # Send metronome results
    message = (
        f"🎼 تشخیص مترونوم:\n"
        f"تعداد ضربات: {metronome_result['num_beats']}\n"
        f"تمپو: {metronome_result['tempo']:.1f} BPM\n"
        f"✅ تحلیل مترونوم کامل شد"
    )
    await update.message.reply_text(message)
    print(f"Metronome: {metronome_result['num_beats']} beats at {metronome_result['tempo']:.1f} BPM")
    
    # Create metronome visualization
    viz_metro_result = visualize_metronome_detection(
        result['y'], 
        result['sr'], 
        metronome_result['beat_times'],
        filepath
    )
    
    if viz_metro_result['success']:
        with open(viz_metro_result['plot_path'], 'rb') as photo:
            await update.message.reply_photo(
                photo=photo,
                caption="شکل موج با ضربات مترونوم مشخص شده"
            )
        print(f"Metronome visualization sent: {viz_metro_result['plot_path']}")
    
    # Extract pitch
    await update.message.reply_text(msg.EXTRACTING_PITCH)
    pitch_result = extract_pitch(result['y'], result['sr'])
    
    if not pitch_result['success']:
        await update.message.reply_text(f"❌ خطا در استخراج نت‌ها: {pitch_result['error']}")
        print(f"Pitch error: {pitch_result['error']}")
        return
    
    # Send pitch analysis results
    freq_min, freq_max = pitch_result['frequency_range']
    message = (
        f"🎵 تحلیل نت‌ها:\n"
        f"تعداد فریم: {pitch_result['num_frames']}\n"
        f"محدوده فرکانس: {freq_min:.1f} - {freq_max:.1f} Hz\n"
        f"✅ استخراج نت‌ها کامل شد"
    )
    await update.message.reply_text(message)
    print(f"Pitch: {pitch_result['num_frames']} frames, {freq_min:.1f}-{freq_max:.1f} Hz")
    
    # Identify notes
    await update.message.reply_text(msg.IDENTIFYING_NOTES)
    note_result = identify_notes(pitch_result['df'])
    
    if not note_result['success']:
        await update.message.reply_text(f"❌ خطا در شناسایی نت‌ها: {note_result['error']}")
        print(f"Note identification error: {note_result['error']}")
        return
    
    # Get top 5 most common notes
    top_notes = sorted(
        note_result['note_counts'].items(), 
        key=lambda x: x[1], 
        reverse=True
    )[:5]
    top_notes_str = "، ".join([f"{note} ({count})" for note, count in top_notes])
    
    # Send note identification results
    message = (
        f"🎹 شناسایی نت‌ها:\n"
        f"تعداد نت‌های مختلف: {note_result['unique_notes']}\n"
        f"نت‌های پرتکرار: {top_notes_str}\n"
        f"میانگین انحراف کوک: {note_result['avg_cents_off']:.1f} سنت\n"
        f"✅ شناسایی نت‌ها کامل شد"
    )
    await update.message.reply_text(message)
    print(f"Notes: {note_result['unique_notes']} unique, avg deviation {note_result['avg_cents_off']:.1f} cents")
    
    # Segment notes
    await update.message.reply_text(msg.SEGMENTING_NOTES)
    segment_result = segment_notes(note_result['df'], result['y'], result['sr'])
    
    if not segment_result['success']:
        await update.message.reply_text(f"❌ خطا در تقسیم‌بندی: {segment_result['error']}")
        print(f"Note segmentation error: {segment_result['error']}")
        return
    
    message = (
        f"🎵 تقسیم‌بندی نت‌ها:\n"
        f"تعداد شروع نت: {segment_result['num_onsets']}\n"
        f"تعداد نت‌های مجزا: {segment_result['num_notes']}\n"
        f"✅ تقسیم‌بندی کامل شد"
    )
    await update.message.reply_text(message)
    print(f"Segmentation: {segment_result['num_notes']} notes from {segment_result['num_onsets']} onsets")
    
    # Calculate timing accuracy
    await update.message.reply_text(msg.ANALYZING_TIMING)
    timing_result = calculate_timing_accuracy(segment_result['notes'], metronome_result['beat_times'])
    
    if timing_result['success']:
        message = (
            f"⏱️ تحلیل تایمینگ:\n"
            f"میانگین خطای تایمینگ: {timing_result['avg_timing_error']:.1f} میلی‌ثانیه\n"
            f"نت‌های روی ضرب: {timing_result['on_beat_percentage']:.1f}%\n"
            f"✅ تحلیل تایمینگ کامل شد"
        )
        await update.message.reply_text(message)
        print(f"Timing: {timing_result['avg_timing_error']:.1f}ms error, {timing_result['on_beat_percentage']:.1f}% on beat")
    
    # Create comprehensive pitch visualization
    await update.message.reply_text(msg.GENERATING_VISUALIZATION)
    viz_result = visualize_pitch_and_notes(
        segment_result['df'],
        timing_result['notes_with_timing'] if timing_result['success'] else segment_result['notes'],
        metronome_result['beat_times'],
        filepath
    )
    
    if not viz_result['success']:
        await update.message.reply_text(f"❌ خطا در ساخت نمودار: {viz_result['error']}")
        print(f"Pitch visualization error: {viz_result['error']}")
        return
    
    # Send the pitch analysis visualization
    with open(viz_result['plot_path'], 'rb') as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=f"گزارش تحلیل کامل - {piece_name}"
        )
    print(f"Pitch visualization sent: {viz_result['plot_path']}")
    
    # Generate video report
    await update.message.reply_text(msg.GENERATING_VIDEO)
    video_output = filepath.replace('.ogg', '_report.mp4')
    
    video_result = generate_video_report(
        segment_result['df'],
        segment_result['notes'],
        metronome_result['beat_times'],
        filepath,
        video_output
    )
    
    if not video_result['success']:
        await update.message.reply_text(f"❌ خطا در ساخت ویدیو: {video_result['error']}")
        print(f"Video generation error: {video_result['error']}")
        return
    
    # Send video report
    await update.message.reply_text(msg.UPLOADING_VIDEO)
    
    file_size_mb = os.path.getsize(video_result['video_path']) / (1024 * 1024)
    print(f"Video file size: {file_size_mb:.2f} MB")
    
    try:
        with open(video_result['video_path'], 'rb') as video:
            await update.message.reply_video(
                video=video,
                caption=f"🎻 گزارش ویدیویی تمرین\n🎼 قطعه: {piece_name}\n⏱️ مدت: {video_result['duration']:.1f}s",
                supports_streaming=True,
                read_timeout=60,
                write_timeout=120
            )
        print(f"✓ Video report sent successfully!")
    except Exception as upload_error:
        print(f"Upload error: {upload_error}")
        await update.message.reply_text(
            f"⚠️ ویدیو ساخته شد ولی آپلود ناموفق بود.\n"
            f"حجم فایل: {file_size_mb:.1f}MB\n\n"
            f"برای فایل‌های بلندتر از ۱ دقیقه، ممکنه حجم زیاد باشه."
        )
    
    # Clear conversation context
    context.user_data.clear()


def main():
    """Start the bot"""
    # Create the Application with increased timeouts for video uploads
    app = Application.builder().token(BOT_TOKEN).read_timeout(30).write_timeout(60).build()
    
    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start_command),
            CallbackQueryHandler(button_callback, pattern='^new_practice$')
        ],
        states={
            State.INSTRUMENT: [CallbackQueryHandler(button_callback)],
            State.PIECE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_piece_name)],
            State.WAITING_AUDIO: [
                MessageHandler(filters.VOICE | filters.AUDIO | filters.VIDEO, receive_audio),
                MessageHandler(filters.ALL, invalid_input)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel_command)],
        allow_reentry=True
    )
    
    # Add handlers
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    print(f"🤖 Practice Buddy Bot v{VERSION} is running... Press Ctrl+C to stop")
    
    # Start the bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()