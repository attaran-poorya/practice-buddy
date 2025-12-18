"""Farsi messages for Practice Buddy Bot"""

# Welcome and help messages
WELCOME = """🎼 سلام! به PracticeMate خوش اومدی

من کمکت می‌کنم تمرین‌هات رو تحلیل کنم و گزارش بگیری.

امروز دوست داری چی کار کنی؟"""

HELP = """📖 راهنمای استفاده

۱. ابتدا سازت رو انتخاب کن
۲. اسم قطعه رو بنویس  
۳. فایل صوتی تمرینت رو بفرست

من برات:
• تمپو و ثبات ریتم
• دقت نت‌ها (کوک یا ناکوک)
• دقت تایمینگ با مترونوم
رو تحلیل می‌کنم و گزارش می‌دم.

دستورات:
/start - شروع مجدد
/help - راهنما
/cancel - لغو عملیات جاری"""

# Conversation prompts
ASK_INSTRUMENT = "چه سازی تمرین می‌کنی؟"

ASK_PIECE_NAME = """عالی! 👌
اسم قطعه‌ای که تمرین می‌کنی چیه؟

✏️ لطفاً نام قطعه رو بنویس."""

ASK_AUDIO = """عالی!
حالا لطفاً فایل صوتی یا ویس تمرین امروزت رو بفرست 🎧

(می‌تونی ویس، فایل صوتی یا ویدیو ارسال کنی.)"""

FILE_RECEIVED = """🎵 فایل دریافت شد!
⏳ در حال تحلیل اجرای شما…

این کار ممکنه تا ۱ دقیقه طول بکشه."""

# Custom instrument message
CUSTOM_INSTRUMENT = """ممنون از علاقه‌ت! 🎶

فعلاً فقط ویولن رو پشتیبانی می‌کنیم، ولی خیلی دوست داریم سازهای دیگه رو هم اضافه کنیم.

اگر دوست داری ساز خودت رو اضافه کنی، می‌تونی توی پروژه GitHub ما مشارکت کنی:
https://github.com/attaran-poorya/practice-buddy

فعلاً می‌خوای با ویولن ادامه بدیم؟"""

# Progress messages
ANALYZING_AUDIO = "🎵 در حال تحلیل صدا..."
DETECTING_METRONOME = "🎯 در حال تشخیص مترونوم..."
EXTRACTING_PITCH = "🎼 در حال استخراج نت‌ها..."
IDENTIFYING_NOTES = "🎹 در حال شناسایی نت‌ها..."
SEGMENTING_NOTES = "🎵 در حال تقسیم‌بندی نت‌ها..."
ANALYZING_TIMING = "⏱️ در حال تحلیل تایمینگ..."
GENERATING_VISUALIZATION = "📊 در حال ساخت نمودار..."
GENERATING_VIDEO = "🎬 در حال ساخت ویدیو گزارش..."
UPLOADING_VIDEO = "📤 در حال آپلود ویدیو..."

# Error messages
ERROR_NO_AUDIO = "لطفاً یک فایل صوتی یا ویس بفرست."
ERROR_ANALYSIS_FAILED = "متأسفانه در تحلیل مشکلی پیش اومد. لطفاً دوباره امتحان کن."
CONVERSATION_CANCELLED = "عملیات لغو شد. برای شروع مجدد /start رو بزن."

# Feedback
FEEDBACK_PROMPT = """
✅ تحلیل تمرین تموم شد!

اگر مشکلی داشتی یا پیشنهادی داری، لطفاً به من بگو.
با /start می‌تونی تمرین جدید بفرستی.
"""

# Button labels
BTN_NEW_PRACTICE = "🎵 ارسال تمرین جدید"
BTN_HELP = "📚 راهنما"
BTN_VIOLIN = "🎻 ویولن"
BTN_CUSTOM_INSTRUMENT = "➕ ساز دیگری"
BTN_YES_VIOLIN = "✅ بله، ویولن"
BTN_CANCEL = "❌ انصراف"
BTN_FULL_ANALYSIS = "📊 تحلیل کامل"
BTN_SKIP_ANALYSIS = "⏭️ رد شدن"

# Quick analysis messages
METRONOME_DETECTED = "✅ مترونوم تشخیص داده شد"
METRONOME_NOT_DETECTED = "❌ مترونوم تشخیص داده نشد"

QUICK_ANALYSIS_RESULT = """📋 نتیجه تحلیل اولیه

🎻 ساز: {instrument}
🎼 قطعه: {piece_name}
⏱️ مدت: {duration:.1f} ثانیه

{metronome_status}
🥁 تعداد ضربات: {num_beats}
🎯 تمپو: {tempo:.1f} BPM

آیا می‌خوای تحلیل کامل انجام بدم؟"""

ANALYSIS_CANCELLED = "✅ متوجه شدم. هر وقت خواستی تمرین جدید بفرست!"
STARTING_FULL_ANALYSIS = "🔄 شروع تحلیل کامل..."