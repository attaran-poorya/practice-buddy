"""Conversation handler for Practice Buddy Bot"""
from enum import IntEnum
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import messages as msg


class State(IntEnum):
    """Conversation states"""
    INSTRUMENT = 1
    PIECE_NAME = 2
    WAITING_AUDIO = 3


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    keyboard = [
        [InlineKeyboardButton(msg.BTN_NEW_PRACTICE, callback_data='new_practice')],
        [InlineKeyboardButton(msg.BTN_HELP, callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(msg.WELCOME, reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    await update.message.reply_text(msg.HELP)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command"""
    # Clear conversation data
    context.user_data.clear()
    
    await update.message.reply_text(msg.CONVERSATION_CANCELLED)
    return -1  # End conversation


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'new_practice':
        return await ask_instrument(update, context, query=query)
    
    elif query.data == 'help':
        await query.edit_message_text(msg.HELP)
        return -1  # End conversation
    
    elif query.data == 'violin':
        context.user_data['instrument'] = 'ویولن'
        await query.edit_message_text(msg.ASK_PIECE_NAME)
        return State.PIECE_NAME
    
    elif query.data == 'custom_instrument':
        keyboard = [
            [InlineKeyboardButton(msg.BTN_YES_VIOLIN, callback_data='violin')],
            [InlineKeyboardButton(msg.BTN_CANCEL, callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(msg.CUSTOM_INSTRUMENT, reply_markup=reply_markup)
        return State.INSTRUMENT
    
    elif query.data == 'cancel':
        await query.edit_message_text(msg.CONVERSATION_CANCELLED)
        context.user_data.clear()
        return -1  # End conversation


async def ask_instrument(update: Update, context: ContextTypes.DEFAULT_TYPE, query=None):
    """Ask user to select instrument"""
    keyboard = [
        [InlineKeyboardButton(msg.BTN_VIOLIN, callback_data='violin')],
        [InlineKeyboardButton(msg.BTN_CUSTOM_INSTRUMENT, callback_data='custom_instrument')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg.ASK_INSTRUMENT, reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg.ASK_INSTRUMENT, reply_markup=reply_markup)
    
    return State.INSTRUMENT


async def receive_piece_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and store piece name"""
    piece_name = update.message.text
    context.user_data['piece_name'] = piece_name
    
    await update.message.reply_text(msg.ASK_AUDIO)
    
    return State.WAITING_AUDIO


async def receive_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle audio file - store context and pass to main handler"""
    # Store context for later use
    instrument = context.user_data.get('instrument', 'نامشخص')
    piece_name = context.user_data.get('piece_name', 'نامشخص')
    
    # Store in context for the analysis handler
    context.user_data['analysis_context'] = {
        'instrument': instrument,
        'piece_name': piece_name
    }
    
    # Important: Mark that we're in analysis mode
    context.user_data['in_conversation'] = True
    
    # Don't send "file received" here - let the main handler do it
    # The main handler will be called automatically after this returns
    
    return -1  # End conversation, let main handler take over


async def invalid_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle invalid input during conversation"""
    await update.message.reply_text(msg.ERROR_NO_AUDIO)
    return State.WAITING_AUDIO