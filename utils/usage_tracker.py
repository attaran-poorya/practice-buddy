"""Simple usage tracking for analytics"""
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

USAGE_LOG_FILE = "usage_stats.log"


def log_user_action(user_id: int, username: str, action: str, details: dict = None):
    """Log user actions for analytics"""
    timestamp = datetime.now().isoformat()
    
    log_entry = {
        'timestamp': timestamp,
        'user_id': user_id,
        'username': username,
        'action': action,
        'details': details or {}
    }
    
    # Log to file
    with open(USAGE_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{log_entry}\n")
    
    # Also log to console
    logger.info(f"USER ACTION: {username} ({user_id}) - {action}")


def log_analysis_complete(user_id: int, username: str, stats: dict):
    """Log completed analysis with stats"""
    log_user_action(user_id, username, "analysis_complete", stats)


def log_error(user_id: int, username: str, error: str):
    """Log errors for debugging"""
    log_user_action(user_id, username, "error", {'error': error})