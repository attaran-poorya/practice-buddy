"""Simple rate limiter to prevent abuse"""
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Track and limit user requests"""
    
    def __init__(self, max_requests_per_hour=10):
        self.max_requests = max_requests_per_hour
        self.user_requests = defaultdict(list)  # user_id -> [timestamps]
    
    def can_proceed(self, user_id: int) -> tuple[bool, str]:
        """Check if user can make another request"""
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        # Clean old requests
        self.user_requests[user_id] = [
            ts for ts in self.user_requests[user_id] 
            if ts > one_hour_ago
        ]
        
        # Check limit
        if len(self.user_requests[user_id]) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for user {user_id}")
            return False, f"لطفاً کمی صبر کن. حداکثر {self.max_requests} تمرین در ساعت می‌تونی بفرستی."
        
        # Add new request
        self.user_requests[user_id].append(now)
        return True, ""
    
    def get_usage(self, user_id: int) -> int:
        """Get current usage count"""
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        self.user_requests[user_id] = [
            ts for ts in self.user_requests[user_id] 
            if ts > one_hour_ago
        ]
        
        return len(self.user_requests[user_id])


# Global rate limiter instance
rate_limiter = RateLimiter(max_requests_per_hour=10)