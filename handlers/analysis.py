"""Analysis handler - processes voice messages and generates reports"""
import os
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from config import VOICE_FOLDER
from audio_processing import (
    load_audio, 
    detect_metronome, 
    extract_pitch, 
    identify_notes, 
    segment_notes, 
    calculate_timing_accuracy
)
from visualization import visualize_metronome_detection, visualize_pitch_and_notes
from video_generation import generate_video_report
import messages as msg

logger = logging.getLogger(__name__)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming voice messages - main entry point"""
    
    # Get context from conversation if available
    analysis_context = context.user_data.get('analysis_context', {})
    instrument = analysis_context.get('instrument', 'نامشخص')
    piece_name = analysis_context.get('piece_name', 'نامشخص')
    
    logger.info(f"=== ANALYSIS START ===")
    logger.info(f"Instrument: {instrument}, Piece: {piece_name}")
    
    voice = update.message.voice
    
    # Download voice file
    file = await context.bot.get_file(voice.file_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"voice_{timestamp}.ogg"
    filepath = os.path.join(VOICE_FOLDER, filename)
    
    logger.info(f"Downloading to {filepath}...")
    await file.download_to_drive(filepath)
    logger.info(f"✓ Downloaded: {filename}")
    
    await update.message.reply_text(msg.FILE_RECEIVED)
    
    # Run analysis pipeline
    try:
        await analyze_audio(update, filepath, instrument, piece_name)
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        await update.message.reply_text(f"❌ {msg.ERROR_ANALYSIS_FAILED}")
    finally:
        # Clear conversation context
        context.user_data.clear()


async def analyze_audio(update: Update, filepath: str, instrument: str, piece_name: str):
    """Run the full analysis pipeline"""
    
    # Step 1: Load audio
    logger.info("Step 1: Loading audio...")
    await update.message.reply_text(msg.ANALYZING_AUDIO)
    result = load_audio(filepath)
    
    if not result['success']:
        logger.error(f"Audio load failed: {result['error']}")
        await update.message.reply_text(f"❌ {msg.ERROR_ANALYSIS_FAILED}\n{result['error']}")
        return
    
    logger.info(f"✓ Audio loaded: {result['duration']:.2f}s @ {result['sample_rate']}Hz")
    
    message = (
        f"📊 تحلیل صوتی\n"
        f"مدت: {result['duration']:.2f} ثانیه\n"
        f"نرخ نمونه‌برداری: {result['sample_rate']} Hz\n"
        f"✅ فایل صوتی بارگذاری شد"
    )
    await update.message.reply_text(message)
    
    # Step 2: Detect metronome
    logger.info("Step 2: Detecting metronome...")
    await update.message.reply_text(msg.DETECTING_METRONOME)
    metronome_result = detect_metronome(result['y'], result['sr'])
    
    if not metronome_result['success']:
        logger.error(f"Metronome detection failed: {metronome_result['error']}")
        await update.message.reply_text(f"❌ خطا در تشخیص مترونوم: {metronome_result['error']}")
        return
    
    logger.info(f"✓ Metronome: {metronome_result['num_beats']} beats @ {metronome_result['tempo']:.1f} BPM")
    
    message = (
        f"🎼 تشخیص مترونوم:\n"
        f"تعداد ضربات: {metronome_result['num_beats']}\n"
        f"تمپو: {metronome_result['tempo']:.1f} BPM\n"
        f"✅ تحلیل مترونوم کامل شد"
    )
    await update.message.reply_text(message)
    
    # Create metronome visualization
    viz_metro_result = visualize_metronome_detection(
        result['y'], result['sr'], metronome_result['beat_times'], filepath
    )
    
    if viz_metro_result['success']:
        with open(viz_metro_result['plot_path'], 'rb') as photo:
            await update.message.reply_photo(photo=photo, caption="شکل موج با ضربات مترونوم")
        logger.info("✓ Metronome visualization sent")
    
    # Step 3: Extract pitch
    logger.info("Step 3: Extracting pitch...")
    await update.message.reply_text(msg.EXTRACTING_PITCH)
    pitch_result = extract_pitch(result['y'], result['sr'])
    
    if not pitch_result['success']:
        logger.error(f"Pitch extraction failed: {pitch_result['error']}")
        await update.message.reply_text(f"❌ خطا در استخراج نت‌ها: {pitch_result['error']}")
        return
    
    freq_min, freq_max = pitch_result['frequency_range']
    logger.info(f"✓ Pitch extracted: {pitch_result['num_frames']} frames, {freq_min:.1f}-{freq_max:.1f} Hz")
    
    message = (
        f"🎵 تحلیل نت‌ها:\n"
        f"تعداد فریم: {pitch_result['num_frames']}\n"
        f"محدوده فرکانس: {freq_min:.1f} - {freq_max:.1f} Hz\n"
        f"✅ استخراج نت‌ها کامل شد"
    )
    await update.message.reply_text(message)
    
    # Step 4: Identify notes
    logger.info("Step 4: Identifying notes...")
    await update.message.reply_text(msg.IDENTIFYING_NOTES)
    note_result = identify_notes(pitch_result['df'])
    
    if not note_result['success']:
        logger.error(f"Note identification failed: {note_result['error']}")
        await update.message.reply_text(f"❌ خطا در شناسایی نت‌ها: {note_result['error']}")
        return
    
    logger.info(f"✓ Notes identified: {note_result['unique_notes']} unique, avg {note_result['avg_cents_off']:.1f} cents")
    
    top_notes = sorted(note_result['note_counts'].items(), key=lambda x: x[1], reverse=True)[:5]
    top_notes_str = "، ".join([f"{note} ({count})" for note, count in top_notes])
    
    message = (
        f"🎹 شناسایی نت‌ها:\n"
        f"تعداد نت‌های مختلف: {note_result['unique_notes']}\n"
        f"نت‌های پرتکرار: {top_notes_str}\n"
        f"میانگین انحراف کوک: {note_result['avg_cents_off']:.1f} سنت\n"
        f"✅ شناسایی نت‌ها کامل شد"
    )
    await update.message.reply_text(message)
    
    # Step 5: Segment notes
    logger.info("Step 5: Segmenting notes...")
    await update.message.reply_text(msg.SEGMENTING_NOTES)
    segment_result = segment_notes(note_result['df'], result['y'], result['sr'])
    
    if not segment_result['success']:
        logger.error(f"Segmentation failed: {segment_result['error']}")
        await update.message.reply_text(f"❌ خطا در تقسیم‌بندی: {segment_result['error']}")
        return
    
    logger.info(f"✓ Segmented: {segment_result['num_notes']} notes from {segment_result['num_onsets']} onsets")
    
    message = (
        f"🎵 تقسیم‌بندی نت‌ها:\n"
        f"تعداد شروع نت: {segment_result['num_onsets']}\n"
        f"تعداد نت‌های مجزا: {segment_result['num_notes']}\n"
        f"✅ تقسیم‌بندی کامل شد"
    )
    await update.message.reply_text(message)
    
    # Step 6: Timing accuracy
    logger.info("Step 6: Analyzing timing...")
    await update.message.reply_text(msg.ANALYZING_TIMING)
    timing_result = calculate_timing_accuracy(segment_result['notes'], metronome_result['beat_times'])
    
    if timing_result['success']:
        logger.info(f"✓ Timing: {timing_result['avg_timing_error']:.1f}ms error, {timing_result['on_beat_percentage']:.1f}% on beat")
        
        message = (
            f"⏱️ تحلیل تایمینگ:\n"
            f"میانگین خطای تایمینگ: {timing_result['avg_timing_error']:.1f} میلی‌ثانیه\n"
            f"نت‌های روی ضرب: {timing_result['on_beat_percentage']:.1f}%\n"
            f"✅ تحلیل تایمینگ کامل شد"
        )
        await update.message.reply_text(message)
    
    # Step 7: Generate visualization
    logger.info("Step 7: Generating visualization...")
    await update.message.reply_text(msg.GENERATING_VISUALIZATION)
    viz_result = visualize_pitch_and_notes(
        segment_result['df'],
        timing_result['notes_with_timing'] if timing_result['success'] else segment_result['notes'],
        metronome_result['beat_times'],
        filepath
    )
    
    if viz_result['success']:
        with open(viz_result['plot_path'], 'rb') as photo:
            await update.message.reply_photo(photo=photo, caption=f"گزارش تحلیل کامل - {piece_name}")
        logger.info("✓ Pitch visualization sent")
    
    # Step 8: Generate video
    logger.info("Step 8: Generating video...")
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
        logger.error(f"Video generation failed: {video_result['error']}")
        await update.message.reply_text(f"❌ خطا در ساخت ویدیو: {video_result['error']}")
        return
    
    # Step 9: Upload video
    logger.info("Step 9: Uploading video...")
    await update.message.reply_text(msg.UPLOADING_VIDEO)
    
    file_size_mb = os.path.getsize(video_result['video_path']) / (1024 * 1024)
    logger.info(f"Video size: {file_size_mb:.2f} MB")
    
    try:
        with open(video_result['video_path'], 'rb') as video:
            await update.message.reply_video(
                video=video,
                caption=f"🎻 گزارش ویدیویی تمرین\n🎼 قطعه: {piece_name}\n⏱️ مدت: {video_result['duration']:.1f}s",
                supports_streaming=True,
                read_timeout=60,
                write_timeout=120
            )
        logger.info("✓ Video uploaded successfully")
    except Exception as upload_error:
        logger.error(f"Video upload failed: {upload_error}")
        await update.message.reply_text(
            f"⚠️ ویدیو ساخته شد ولی آپلود ناموفق بود.\n"
            f"حجم فایل: {file_size_mb:.1f}MB"
        )
    
    logger.info("=== ANALYSIS COMPLETE ===")