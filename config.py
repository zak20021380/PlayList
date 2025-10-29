# config.py - Bot Configuration
# تنظیمات ربات

import os

# ====== BOT TOKEN ======
# از @BotFather بگیر
BOT_TOKEN = "8351980310:AAF9WuKI6J7WTBCuLmzA97XZK-OhJVRCXO8"  # جایگزین کن با توکن واقعی

# ====== ADMIN IDS ======
# آیدی تلگرام خودت رو از @userinfobot بگیر
ADMIN_IDS = [1350508522]  # آیدی تلگرام خودت رو اینجا بذار

# ====== PREMIUM SETTINGS ======
PREMIUM_PRICE = 200000  # قیمت به تومان
PREMIUM_DURATION_DAYS = 30  # مدت اشتراک (روز)

# ====== FREE USER LIMITS ======
FREE_PLAYLIST_LIMIT = 5
FREE_UPLOAD_LIMIT = 50
FREE_FOLLOW_LIMIT = 50

# ====== PREMIUM USER LIMITS ======
PREMIUM_PLAYLIST_LIMIT = 999
PREMIUM_UPLOAD_LIMIT = 9999
PREMIUM_FOLLOW_LIMIT = 999

# ====== DATABASE ======
DATABASE_PATH = "data/users.json"

# Create data directory
if not os.path.exists("data"):
    os.makedirs("data")

# ====== MOODS ======
DEFAULT_MOODS = {
    'happy': '😊 شاد',
    'sad': '😢 غمگین',
    'chill': '😌 آرامش',
    'party': '🔥 پارتی',
    'workout': '💪 ورزشی',
    'romantic': '💖 عاشقانه',
    'angry': '😤 عصبانی',
    'focus': '🎯 تمرکز',
}

# ====== BADGES ======
BADGES = {
    'first_playlist': '🎵 اولین پلی‌لیست',
    'popular': '🔥 محبوب',
    'viral': '💫 وایرال',
    'premium': '💎 پریمیوم',
    'curator_king': '👑 پادشاه',
}

# ====== SETTINGS ======
LEADERBOARD_TOP_COUNT = 20
ENABLE_NOTIFICATIONS = True
BOT_NAME = "پلی‌لیست"
BOT_USERNAME = "@playlist_bot"

# ====== ZARINPAL PAYMENT GATEWAY ======
ZARINPAL_MERCHANT_ID = "d97f7648-614f-4025-bee2-5f3cda6d8fcd"  # مرچنت آیدی زرین‌پال
ZARINPAL_CALLBACK_URL = "https://yourdomain.com/verify"  # آدرس کال‌بک (بعداً تنظیم میکنیم)
ZARINPAL_SANDBOX = False  # True = تست، False = واقعی

# ZarinPal API URLs
ZARINPAL_REQUEST_URL = "https://api.zarinpal.com/pg/v4/payment/request.json"
ZARINPAL_VERIFY_URL = "https://api.zarinpal.com/pg/v4/payment/verify.json"
ZARINPAL_PAYMENT_URL = "https://www.zarinpal.com/pg/StartPay/"

# Sandbox URLs (for testing)
ZARINPAL_SANDBOX_REQUEST_URL = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
ZARINPAL_SANDBOX_VERIFY_URL = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"
ZARINPAL_SANDBOX_PAYMENT_URL = "https://sandbox.zarinpal.com/pg/StartPay/"