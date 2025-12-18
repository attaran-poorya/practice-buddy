"""Full analysis handler - detailed pitch and timing analysis"""
import os
import logging

from telegram import Update
from telegram.ext import ContextTypes

from audio_processing import (
    extract_pitch, 
    identify_notes, 
    segment_notes, 
    calculate_timing_accuracy
)
from visualization import visualize_metronome_detection, visualize_pitch_and_notes
from video_generation import generate_video_report
import messages as msg
from utils.usage_tracker import log_analysis_complete

logger = logging.getLogger(__name__)


async def run_full_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE, quick_data: dict):
    """Run complete detailed analysis using quick analysis data"""
    
    # Extract data
    filepath = quick_data['filepath']
    instrument = quick_data['instrument']
    piece_name = quick_data['piece_name']
    user_id = quick_data['user_id']
    username = quick_data['username']
    result = quick_data['audio_data']
    metronome_result = quick_data['metronome_result']
    
    logger.info("=== FULL ANALYSIS START ===")
    stats = {'duration': result['duration']}
    
    # We already have audio loaded and metronome detected from quick analysis
    if metronome_result:
        stats['num_beats'] = metronome_result['num_beats']
        stats['tempo'] = metronome_result['tempo']
        
        # Show metronome viz
        viz_metro_result = visualize_metronome_detection(
            result['y'], result['sr'], metronome_result['beat_times'], filepath
        )
        
        if viz_metro_result['success']:
            with open(viz_metro_result['plot_path'], 'rb') as photo:
                await update.callback_query.message.reply_photo(
                    photo=photo, 
                    caption="شکل موج با ضربات مترونوم"
                )
            logger.info("✓ Metronome visualization sent")
    
    # Step 3: Extract pitch
    logger.info("Step 3: Extracting pitch...")
    await update.callback_query.message.reply_text(msg.EXTRACTING_PITCH)
    pitch_result = extract_pitch(result['y'], result['sr'])
    
    if not pitch_result['success']:
        logger.error(f"Pitch extraction failed: {pitch_result['error']}")
        await update.callback_query.message.reply_text(f"❌ خطا در استخراج نت‌ها")
        return
    
    freq_min, freq_max = pitch_result['frequency_range']
    logger.info(f"✓ Pitch extracted: {pitch_result['num_frames']} frames")
    
    # Step 4: Identify notes
    logger.info("Step 4: Identifying notes...")
    await update.callback_query.message.reply_text(msg.IDENTIFYING_NOTES)
    note_result = identify_notes(pitch_result['df'])
    
    if not note_result['success']:
        logger.error(f"Note identification failed")
        await update.callback_query.message.reply_text(f"❌ خطا در شناسایی نت‌ها")
        return
    
    logger.info(f"✓ Notes identified: {note_result['unique_notes']} unique")
    stats['avg_cents_off'] = note_result['avg_cents_off']
    stats['unique_notes'] = note_result['unique_notes']
    
    top_notes = sorted(note_result['note_counts'].items(), key=lambda x: x[1], reverse=True)[:5]
    top_notes_str = "، ".join([f"{note} ({count})" for note, count in top_notes])
    
    message = (
        f"🎹 شناسایی نت‌ها:\n"
        f"تعداد نت‌های مختلف: {note_result['unique_notes']}\n"
        f"نت‌های پرتکرار: {top_notes_str}\n"
        f"میانگین انحراف کوک: {note_result['avg_cents_off']:.1f} سنت"
    )
    await update.callback_query.message.reply_text(message)
    
    # Step 5: Segment notes
    logger.info("Step 5: Segmenting notes...")
    await update.callback_query.message.reply_text(msg.SEGMENTING_NOTES)
    segment_result = segment_notes(note_result['df'], result['y'], result['sr'])
    
    if not segment_result['success']:
        logger.error(f"Segmentation failed")
        await update.callback_query.message.reply_text(f"❌ خطا در تقسیم‌بندی")
        return
    
    logger.info(f"✓ Segmented: {segment_result['num_notes']} notes")
    stats['num_notes'] = segment_result['num_notes']
    
    # Step 6: Timing accuracy (only if metronome exists)
    timing_result = None
    if metronome_result:
        logger.info("Step 6: Analyzing timing...")
        await update.callback_query.message.reply_text(msg.ANALYZING_TIMING)
        timing_result = calculate_timing_accuracy(
            segment_result['notes'], 
            metronome_result['beat_times']
        )
        
        if timing_result['success']:
            logger.info(f"✓ Timing: {timing_result['avg_timing_error']:.1f}ms error")
            stats['avg_timing_error'] = timing_result['avg_timing_error']
            stats['on_beat_percentage'] = timing_result['on_beat_percentage']
            
            message = (
                f"⏱️ تحلیل تایمینگ:\n"
                f"میانگین خطای تایمینگ: {timing_result['avg_timing_error']:.1f} میلی‌ثانیه\n"
                f"نت‌های روی ضرب: {timing_result['on_beat_percentage']:.1f}%"
            )
            await update.callback_query.message.reply_text(message)
    
    # Step 7: Generate visualization
    logger.info("Step 7: Generating visualization...")
    await update.callback_query.message.reply_text(msg.GENERATING_VISUALIZATION)
    
    beat_times = metronome_result['beat_times'] if metronome_result else []
    notes_with_timing = timing_result['notes_with_timing'] if timing_result and timing_result['success'] else segment_result['notes']
    
    viz_result = visualize_pitch_and_notes(
        segment_result['df'],
        notes_with_timing,
        beat_times,
        filepath
    )
    
    if viz_result['success']:
        with open(viz_result['plot_path'], 'rb') as photo:
            await update.callback_query.message.reply_photo(
                photo=photo, 
                caption=f"گزارش تحلیل کامل - {piece_name}"
            )
        logger.info("✓ Pitch visualization sent")
    
    # Step 8: Generate video
    logger.info("Step 8: Generating video...")
    await update.callback_query.message.reply_text(msg.GENERATING_VIDEO)
    video_output = filepath.replace('.ogg', '_report.mp4')
    
    video_result = generate_video_report(
        segment_result['df'],
        segment_result['notes'],
        beat_times,
        filepath,
        video_output
    )
    
    if not video_result['success']:
        logger.error(f"Video generation failed")
        await update.callback_query.message.reply_text(f"❌ خطا در ساخت ویدیو")
        log_analysis_complete(user_id, username, stats)
        await update.callback_query.message.reply_text(msg.FEEDBACK_PROMPT)
        return
    
    # Step 9: Upload video
    logger.info("Step 9: Uploading video...")
    await update.callback_query.message.reply_text(msg.UPLOADING_VIDEO)
    
    file_size_mb = os.path.getsize(video_result['video_path']) / (1024 * 1024)
    logger.info(f"Video size: {file_size_mb:.2f} MB")
    
    try:
        with open(video_result['video_path'], 'rb') as video:
            await update.callback_query.message.reply_video(
                video=video,
                caption=f"🎻 گزارش ویدیویی تمرین\n🎼 قطعه: {piece_name}\n⏱️ مدت: {video_result['duration']:.1f}s",
                supports_streaming=True,
                read_timeout=60,
                write_timeout=120
            )
        logger.info("✓ Video uploaded successfully")
        stats['video_uploaded'] = True
    except Exception as upload_error:
        logger.error(f"Video upload failed: {upload_error}")
        stats['video_uploaded'] = False
        await update.callback_query.message.reply_text(
            f"⚠️ ویدیو ساخته شد ولی آپلود ناموفق بود.\n"
            f"حجم فایل: {file_size_mb:.1f}MB"
        )
    
    # Send completion message
    await update.callback_query.message.reply_text(msg.FEEDBACK_PROMPT)
    
    # Log completion
    log_analysis_complete(user_id, username, stats)
    logger.info("=== FULL ANALYSIS COMPLETE ===")