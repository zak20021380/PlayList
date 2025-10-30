# utils.py - Helper Functions & ZarinPal Integration
# توابع کمکی و پرداخت زرین‌پال

import requests
from datetime import datetime
from typing import Optional, Dict

from config import *


# ===== ZARINPAL PAYMENT =====

class ZarinPal:
    """ZarinPal payment gateway handler"""

    def __init__(self):
        self.merchant_id = ZARINPAL_MERCHANT_ID
        self.sandbox = ZARINPAL_SANDBOX

        if self.sandbox:
            self.request_url = ZARINPAL_SANDBOX_REQUEST_URL
            self.verify_url = ZARINPAL_SANDBOX_VERIFY_URL
            self.payment_url = ZARINPAL_SANDBOX_PAYMENT_URL
        else:
            self.request_url = ZARINPAL_REQUEST_URL
            self.verify_url = ZARINPAL_VERIFY_URL
            self.payment_url = ZARINPAL_PAYMENT_URL

    def create_payment(self, amount: int, description: str, user_id: int) -> Optional[str]:
        """
        Create payment request
        Returns: Payment URL or None
        """
        data = {
            "merchant_id": self.merchant_id,
            "amount": amount,
            "description": description,
            "callback_url": f"{ZARINPAL_CALLBACK_URL}?user_id={user_id}",
        }

        try:
            response = requests.post(self.request_url, json=data, timeout=10)
            result = response.json()

            if result.get('data', {}).get('code') == 100:
                authority = result['data']['authority']
                payment_url = f"{self.payment_url}{authority}"
                return payment_url
            else:
                print(f"ZarinPal Error: {result}")
                return None

        except Exception as e:
            print(f"ZarinPal Request Error: {e}")
            return None

    def verify_payment(self, authority: str, amount: int) -> bool:
        """
        Verify payment after callback
        Returns: True if successful
        """
        data = {
            "merchant_id": self.merchant_id,
            "amount": amount,
            "authority": authority
        }

        try:
            response = requests.post(self.verify_url, json=data, timeout=10)
            result = response.json()

            if result.get('data', {}).get('code') == 100:
                return True
            else:
                print(f"ZarinPal Verify Error: {result}")
                return False

        except Exception as e:
            print(f"ZarinPal Verify Error: {e}")
            return False


# Initialize ZarinPal
zarinpal = ZarinPal()


# ===== FORMATTING HELPERS =====

def format_number(num: int) -> str:
    """Format number with commas (1000 -> 1,000)"""
    return f"{num:,}"


def format_date(iso_date: str) -> str:
    """Format ISO date to Persian readable format"""
    try:
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime("%Y/%m/%d")
    except:
        return iso_date


def format_datetime(iso_date: str) -> str:
    """Format ISO datetime to Persian readable format"""
    try:
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime("%Y/%m/%d - %H:%M")
    except:
        return iso_date


def time_ago(iso_date: str) -> str:
    """Get human-readable time ago (e.g., '2 hours ago')"""
    try:
        dt = datetime.fromisoformat(iso_date)
        diff = datetime.now() - dt

        seconds = diff.total_seconds()

        if seconds < 60:
            return "همین الان"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} دقیقه پیش"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} ساعت پیش"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days} روز پیش"
        elif seconds < 2592000:
            weeks = int(seconds / 604800)
            return f"{weeks} هفته پیش"
        else:
            months = int(seconds / 2592000)
            return f"{months} ماه پیش"
    except:
        return "نامشخص"


def format_duration(seconds: int) -> str:
    """Format duration in seconds to MM:SS"""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


# ===== TEXT HELPERS =====

def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text with ellipsis"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def escape_markdown(text: str) -> str:
    """Escape special markdown characters"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def clean_username(username: Optional[str]) -> str:
    """Clean username for display"""
    if not username:
        return "بدون_یوزرنیم"
    return username.replace('@', '')


# ===== VALIDATION =====

def is_valid_playlist_name(name: str) -> bool:
    """Validate playlist name"""
    if not name or len(name) < 2:
        return False
    if len(name) > 100:
        return False
    return True


def is_valid_audio_file(file_size: int, duration: int) -> bool:
    """Validate audio file"""
    # Max 50MB
    if file_size > 50 * 1024 * 1024:
        return False
    # Max 30 minutes
    if duration > 1800:
        return False
    return True


# ===== NOTIFICATION HELPERS =====

def should_send_notification(user_id: int, db) -> bool:
    """Check if user has notifications enabled"""
    user = db.get_user(user_id)
    if not user:
        return False
    return user.get('notifications_enabled', True)


# ===== SHARE LINK HELPERS =====

def build_playlist_deep_link(playlist_id: str) -> str:
    """Return deep link that opens the bot on a specific playlist"""
    username = BOT_USERNAME.lstrip('@') if BOT_USERNAME else ''
    return f"https://t.me/{username}?start={playlist_id}" if username else ""


def build_playlist_share_url(playlist_id: str, playlist_name: str) -> str:
    """Return direct deep link that opens the playlist inside the bot"""
    return build_playlist_deep_link(playlist_id)


# ===== PLAYLIST HELPERS =====

def get_playlist_info(playlist: Dict) -> str:
    """Format playlist info for display"""
    name = playlist['name']
    owner = playlist['owner_name']
    songs_count = len(playlist.get('songs', []))
    likes_count = len(playlist.get('likes', []))
    plays = playlist.get('plays', 0)
    mood = DEFAULT_MOODS.get(playlist.get('mood', 'happy'), '🎵')

    return f"{mood} **{name}**\n👤 {owner} | 🎵 {songs_count} آهنگ | ❤️ {likes_count} | ▶️ {plays}"


def get_song_info(song: Dict) -> str:
    """Format song info for display"""
    title = song.get('title', 'Unknown')
    performer = song.get('performer', 'Unknown')
    duration = format_duration(song.get('duration', 0))

    return f"🎵 {title}\n👤 {performer} | ⏱ {duration}"


# ===== RANKING HELPERS =====

def get_rank_emoji(rank: int) -> str:
    """Get emoji for rank"""
    if rank == 1:
        return "🥇"
    elif rank == 2:
        return "🥈"
    elif rank == 3:
        return "🥉"
    else:
        return f"{rank}."


def calculate_score(user: Dict) -> int:
    """Calculate user score for ranking"""
    likes = user.get('total_likes_received', 0)
    plays = user.get('total_plays', 0)
    songs = user.get('total_songs_uploaded', 0)

    # Weighted score
    return (likes * 10) + (plays * 2) + songs


# ===== BADGE HELPERS =====

def format_badges(badge_list: list) -> str:
    """Format badges for display"""
    if not badge_list:
        return "هنوز بجی نداری!"

    badges_text = []
    for badge_key in badge_list:
        badge_name = BADGES.get(badge_key, '')
        if badge_name:
            badges_text.append(badge_name)

    return ' '.join(badges_text) if badges_text else "هنوز بجی نداری!"


# ===== ADMIN HELPERS =====

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in ADMIN_IDS


def format_admin_stats(stats: Dict) -> str:
    """Format stats for admin panel"""
    return f"""
📊 **آمار کلی:**

👥 کل کاربرها: {format_number(stats['total_users'])}
✅ فعال امروز: {format_number(stats['active_today'])}
📈 عضو جدید امروز: {format_number(stats['new_today'])}

🎵 کل پلی‌لیست‌ها: {format_number(stats['total_playlists'])}
🎧 کل آهنگ‌ها: {format_number(stats['total_songs'])}
❤️ کل لایک‌ها: {format_number(stats['total_likes'])}
▶️ کل پلی‌ها: {format_number(stats['total_plays'])}

💎 کاربران پریمیوم: {format_number(stats['premium_users'])}
💰 درآمد کل: {format_number(stats['revenue'])} تومان

📅 {datetime.now().strftime("%Y/%m/%d")}
"""


# ===== PAGINATION =====

def paginate_list(items: list, page: int = 1, per_page: int = 10) -> tuple:
    """
    Paginate a list
    Returns: (paginated_items, total_pages, has_next, has_prev)
    """
    total = len(items)
    total_pages = (total + per_page - 1) // per_page

    start = (page - 1) * per_page
    end = start + per_page

    paginated = items[start:end]
    has_next = page < total_pages
    has_prev = page > 1

    return paginated, total_pages, has_next, has_prev


# ===== KEYBOARD HELPERS =====

def create_mood_keyboard():
    """Create mood selection keyboard"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    buttons = []
    row = []
    for mood_key, mood_name in DEFAULT_MOODS.items():
        row.append(InlineKeyboardButton(mood_name, callback_data=f"mood_{mood_key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(buttons)


def create_playlist_buttons(playlist_id: str, user_liked: bool = False):
    """Create interaction buttons for playlist"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    like_text = "💕 لایک شده" if user_liked else "❤️ لایک"

    buttons = [
        [
            InlineKeyboardButton(like_text, callback_data=f"like_{playlist_id}"),
            InlineKeyboardButton("➕ اضافه کن", callback_data=f"add_{playlist_id}"),
        ],
        [
            InlineKeyboardButton("▶️ پلی", callback_data=f"play_{playlist_id}"),
            InlineKeyboardButton("📤 شیر کن", callback_data=f"share_{playlist_id}"),
        ]
    ]

    return InlineKeyboardMarkup(buttons)


def create_song_buttons(
    song_id: str,
    playlist_id: str,
    *,
    user_liked: bool = False,
    already_added: bool = False,
):
    """Create interaction buttons for individual song"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    like_label = "💕 لایک شده" if user_liked else "❤️ لایک"
    add_label = "✅ اضافه شد" if already_added else "➕ اضافه کن"

    buttons = [
        [
            InlineKeyboardButton(
                like_label,
                callback_data=f"like_song_{song_id}",
            ),
            InlineKeyboardButton(
                add_label,
                callback_data=f"add_song:{playlist_id}:{song_id}",
            ),
        ]
    ]

    return InlineKeyboardMarkup(buttons)


# ===== ERROR HANDLING =====

def handle_error(error: Exception, context: str = "") -> str:
    """Handle and log errors"""
    error_msg = f"Error in {context}: {str(error)}"
    print(error_msg)
    return "اوپس! یه مشکلی پیش اومد 😅\n\nدوباره امتحان کن"


# ===== CACHE HELPERS (Simple) =====

_cache = {}


def cache_set(key: str, value, ttl: int = 300):
    """Set cache with TTL in seconds"""
    _cache[key] = {
        'value': value,
        'expires': datetime.now().timestamp() + ttl
    }


def cache_get(key: str):
    """Get from cache"""
    if key in _cache:
        item = _cache[key]
        if datetime.now().timestamp() < item['expires']:
            return item['value']
        else:
            del _cache[key]
    return None


def cache_clear():
    """Clear all cache"""
    _cache.clear()