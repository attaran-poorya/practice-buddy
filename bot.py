"""Practice Buddy Bot - Main entry point"""
import sys
import logging
from telegram.ext import (
    Application, 
    CommandHandler,
    MessageHandler, 
    CallbackQueryHandler,
    ConversationHandler,
    filters
)

from config import BOT_TOKEN, VERSION, VOICE_FOLDER
from handlers.conversation import (
    State,
    start_command,
    help_command,
    cancel_command,
    button_callback,
    receive_piece_name,
    receive_audio,
    invalid_input
)
from handlers.analysis import handle_voice

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger(__name__)


def setup_handlers(app: Application):
    """Setup all bot handlers"""
    
    # Conversation handler for new practice flow
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
        per_message=False,
        per_chat=True,
        per_user=True,
        allow_reentry=True
    )
    
    # Add all handlers
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))  # Direct voice without conversation
    
    logger.info("✓ Handlers registered")


def main():
    """Start the bot"""
    import os
    
    # Create voice_messages folder
    os.makedirs(VOICE_FOLDER, exist_ok=True)
    
    logger.info(f"Starting Practice Buddy Bot v{VERSION}...")
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).read_timeout(30).write_timeout(60).build()
    
    # Setup handlers
    setup_handlers(app)
    
    logger.info(f"🤖 Practice Buddy Bot v{VERSION} is running!")
    print(f"🤖 Practice Buddy Bot v{VERSION} is running!", flush=True)
    
    # Start polling
    app.run_polling(allowed_updates=['message', 'callback_query'])


if __name__ == "__main__":
    main()