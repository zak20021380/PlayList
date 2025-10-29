# texts.py - All Bot Messages in Friendly Persian
# تمام متن‌های ربات به فارسی دوستانه

WELCOME = """
🎵 **سلااام! به پلی‌لیست خوش اومدی!** 🎵

اینجا جای موزیک‌بازیه! میتونی:

✨ پلی‌لیست بسازی و موزیک‌هات رو شیر کنی
🔥 از پلی‌لیست‌های بقیه لذت ببری  
💖 آهنگایی که دوست داری رو لایک کنی
🔔 وقتی کسی موزیک تو رو لایک کنه، بهت خبر بدیم!

**چیکار میتونی بکنی:**

📁 /newplaylist - یه پلی‌لیست جدید بساز
🎵 /myplaylists - پلی‌لیست‌های خودت
🔥 /browse - ببین بقیه چی گوش میدن
📈 /trending - پلی‌لیست‌های ترند
👤 /profile - پروفایل خودت
🏆 /leaderboard - رتبه‌بندی
💎 /premium - پریمیوم بگیر

**برای آپلود آهنگ:**
فقط یه فایل صوتی بفرست و تو کپشن اسم پلی‌لیستت رو بنویس!

بریم که بریم! 🚀
"""

HELP = """
📚 **راهنما**

**دستورات اصلی:**
/start - شروع مجدد
/newplaylist - پلی‌لیست جدید
/myplaylists - پلی‌لیست‌های من
/browse - مرور همه پلی‌لیست‌ها
/trending - پلی‌لیست‌های داغ
/profile - پروفایل من
/leaderboard - رتبه‌بندی
/mystats - آمار من
/settings - تنظیمات
/premium - خرید پریمیوم

**چطوری کار میکنه:**

1️⃣ یه پلی‌لیست بساز (/newplaylist)
2️⃣ فایل صوتی بفرست + تو کپشن اسم پلی‌لیست رو بنویس
3️⃣ پلی‌لیستت آماده‌س!
4️⃣ بقیه میتونن لایک کنن و به پلی‌لیست خودشون اضافه کنن

**نکات:**
- هر موزیکی که آپلود کنی، همه میتونن ببینن
- وقتی کسی موزیکت رو لایک کنه، بهت خبر میدیم
- هرچی بیشتر لایک بگیری، بالاتر میری!

سوالی بود؟ به @support_bot پیام بده
"""

# ===== PLAYLIST MESSAGES =====
NEW_PLAYLIST_START = "خب، میخوای پلی‌لیستت رو چی صدا کنیم؟ 🎵\n\nیه اسم باحال انتخاب کن!"

NEW_PLAYLIST_MOOD = "حالا حال و هوای این پلی‌لیست چیه؟ 🎭"

PLAYLIST_CREATED = "آفرین! پلی‌لیست «{name}» ساخته شد! ✅\n\nحالا میتونی براش موزیک بفرستی 🎵"

PLAYLIST_DELETED = "پلی‌لیست پاک شد 🗑️"

PLAYLIST_LIMIT_REACHED = """
⚠️ اوه! به حد مجاز رسیدی!

کاربر رایگان فقط میتونه {limit} تا پلی‌لیست بسازه.

میخوای نامحدود پلی‌لیست داشته باشی؟
/premium رو بزن! 💎
"""

NO_PLAYLISTS = "هنوز پلی‌لیستی نساختی! 😅\n\nبزن /newplaylist و شروع کن! 🚀"

UPLOAD_SUCCESS = "آهنگ با موفقیت به «{playlist}» اضافه شد! ✅🎵"

UPLOAD_NO_PLAYLIST = """
اسم پلی‌لیستی که نوشتی پیدا نشد! 😕

پلی‌لیست‌های تو:
{playlists}

یا /newplaylist بزن و یه پلی‌لیست جدید بساز!
"""

UPLOAD_LIMIT_REACHED = """
⚠️ حد مجاز آپلود تموم شد!

کاربر رایگان فقط {limit} آهنگ میتونه آپلود کنه.

برای آپلود نامحدود، پریمیوم بگیر:
/premium 💎
"""

# ===== INTERACTION MESSAGES =====
LIKED = "لایک شد! ❤️"

ALREADY_LIKED = "قبلاً لایک کردی! 💕"

UNLIKED = "لایک برداشته شد 💔"

ADDED_TO_PLAYLIST = "به پلی‌لیست «{playlist}» اضافه شد! ✅"

CHOOSE_PLAYLIST_TO_ADD = "به کدوم پلی‌لیستت اضافه کنم؟ 🤔"

# ===== NOTIFICATION MESSAGES =====
NOTIF_LIKED = "🔔 {user} پلی‌لیست «{playlist}» تو رو لایک کرد! ❤️"

NOTIF_ADDED = "🔔 {user} آهنگ «{song}» تو رو به پلی‌لیستش اضافه کرد! 🎵"

NOTIF_MILESTONE = "🎉 وااای! پلی‌لیست «{playlist}» تو به {count} لایک رسید! 🔥"

NOTIF_NEW_FOLLOWER = "🔔 {user} تو رو فالو کرد! 👥"

NOTIF_BADGE_EARNED = "🏆 تبریک! بج «{badge}» رو گرفتی!"

NOTIF_PREMIUM_EXPIRING = "⚠️ {days} روز دیگه پریمیومت تموم میشه! تمدید کن تا از دستش ندی! 💎"

# ===== PROFILE MESSAGES =====
PROFILE_TEXT = """
👤 **پروفایل {name}**

📊 **آمار:**
🎵 {playlists_count} پلی‌لیست
🎧 {songs_count} آهنگ آپلود شده
❤️ {likes_received} لایک گرفته
▶️ {plays_received} پلی شده
👥 {followers} فالوور | {following} فالو میکنه

🏆 **رتبه:** #{rank}
✨ **بج‌ها:** {badges}
💎 **وضعیت:** {status}

📅 عضو از: {join_date}
"""

MY_STATS = """
📊 **آمار من:**

🎵 کل پلی‌لیست‌ها: {playlists}
🎧 کل آهنگ‌ها: {songs}
❤️ کل لایک‌ها: {likes}
▶️ کل پلی‌ها: {plays}
➕ دفعات اضافه شده: {adds}

📈 **این هفته:**
+{new_likes} لایک جدید
+{new_plays} پلی جدید

🔥 **محبوب‌ترین پلی‌لیست:**
«{top_playlist}» با {top_likes} لایک

🏆 رتبه تو: #{rank} از {total}
"""

# ===== LEADERBOARD =====
LEADERBOARD_HEADER = """
🏆 **رتبه‌بندی برترین‌ها** 🏆

{period}

"""

LEADERBOARD_ITEM = "{rank}. {name} - {score} {unit}"

LEADERBOARD_YOUR_RANK = "\n📍 رتبه تو: #{rank}"

# ===== BROWSE/DISCOVER =====
BROWSE_MENU = """
🔍 **دنبال چی میگردی؟**

از دکمه‌های زیر انتخاب کن:
"""

TRENDING_HEADER = "🔥 **پلی‌لیست‌های ترند این هفته:**\n\n"

NEW_PLAYLISTS_HEADER = "✨ **پلی‌لیست‌های تازه:**\n\n"

TOP_PLAYLISTS_HEADER = "👑 **برترین پلی‌لیست‌های همه دوران:**\n\n"

SEARCH_PROMPT = "چی دنبالشی؟ اسمش رو بنویس 🔍"

SEARCH_NO_RESULTS = "چیزی پیدا نشد! 😕\n\nیه چیز دیگه سرچ کن"

# ===== PREMIUM =====
PREMIUM_INFO = """
💎 **پریمیوم بگیر، حال کن!** 💎

**با پریمیوم چی داری:**
✅ پلی‌لیست نامحدود  
✅ آپلود نامحدود
✅ بدون تبلیغات
✅ بج ویژه 💎
✅ آمار پیشرفته
✅ پلی‌لیست خصوصی
✅ اولویت تو صفحه کشف

**قیمت:** {price:,} تومان / ماه

برای خرید /buy رو بزن! 🚀
"""

PREMIUM_PAYMENT_INSTRUCTIONS = """
💳 **خرید پریمیوم:**

قیمت: {price:,} تومان / ماه

برای پرداخت روی دکمه زیر کلیک کن:
👇👇👇

بعد از پرداخت موفق، پریمیومت خودکار فعال میشه! ⚡️

**پرداخت امن با زرین‌پال** 🔒
"""

PREMIUM_ACTIVATED = """
🎉 **یااااس! پریمیوم فعال شد!** 🎉

حالا میتونی:
✨ پلی‌لیست نامحدود بسازی
🚀 آپلود نامحدود داشته باشی
💎 از بج ویژه لذت ببری

پریمیومت تا {date} اعتباره

حال کن! 🔥
"""

ALREADY_PREMIUM = "تو که الان پریمیومی! 💎\n\nپریمیومت تا {date} اعتباره ✅"

# ===== FOLLOW SYSTEM =====
FOLLOWED = "فالو شد! ✅ حالا پست‌های {name} رو میبینی"

UNFOLLOWED = "آنفالو شد ✅"

ALREADY_FOLLOWING = "قبلاً فالو کردی! ✅"

FOLLOWERS_LIST = "👥 **فالوورها:**\n\n{list}"

FOLLOWING_LIST = "👥 **فالو میکنی:**\n\n{list}"

# ===== ERROR MESSAGES =====
ERROR_GENERAL = "اوپس! یه مشکلی پیش اومد 😅\n\nدوباره امتحان کن"

ERROR_NO_AUDIO = "این فایل صوتی نیست! 🎵\n\nیه فایل MP3 یا صوتی دیگه بفرست"

ERROR_NO_CAPTION = "کپشن نذاشتی! 😅\n\nاسم پلی‌لیستت رو تو کپشن بنویس"

ERROR_USER_BANNED = "متاسفانه دسترسیت قطع شده ⛔️\n\nبرای اطلاعات بیشتر با ادمین تماس بگیر"

ERROR_NOT_FOUND = "پیدا نشد! 😕"

# ===== ADMIN MESSAGES =====
ADMIN_PANEL = """
👨‍💼 **پنل ادمین**

از دکمه‌های زیر استفاده کن:
"""

ADMIN_STATS = """
📊 **آمار کلی ربات:**

👥 کل کاربرها: {total_users}
✅ فعال امروز: {active_today}
📈 عضو جدید امروز: {new_today}

🎵 کل پلی‌لیست‌ها: {total_playlists}
🎧 کل آهنگ‌ها: {total_songs}
❤️ کل لایک‌ها: {total_likes}
▶️ کل پلی‌ها: {total_plays}

💎 کاربران پریمیوم: {premium_users}
💰 درآمد کل: {revenue:,} تومان

📅 {date}
"""

ADMIN_USER_INFO = """
👤 **اطلاعات کاربر:**

🆔 آیدی: {user_id}
👤 نام: {name}
📛 یوزرنیم: @{username}

📊 پلی‌لیست‌ها: {playlists}
🎵 آهنگ‌ها: {songs}
❤️ لایک‌ها: {likes}

💎 وضعیت: {status}
🏆 رتبه: #{rank}

📅 عضو از: {join_date}
"""

ADMIN_BROADCAST_SENT = "پیام به {count} کاربر ارسال شد! ✅"

ADMIN_USER_BANNED = "کاربر بن شد ⛔️"

ADMIN_USER_UNBANNED = "بن کاربر برداشته شد ✅"

ADMIN_PREMIUM_GIVEN = "پریمیوم به کاربر داده شد! 💎"

ADMIN_PRICE_CHANGED = "قیمت پریمیوم به {price:,} تومان تغییر کرد ✅"

# ===== BUTTONS =====
BTN_MY_PLAYLISTS = "🎵 پلی‌لیست‌های من"
BTN_BROWSE = "🔍 مرور"
BTN_TRENDING = "🔥 ترند"
BTN_PROFILE = "👤 پروفایل"
BTN_LEADERBOARD = "🏆 رتبه‌بندی"
BTN_PREMIUM = "💎 پریمیوم"
BTN_HELP = "❓ راهنما"
BTN_SETTINGS = "⚙️ تنظیمات"

BTN_LIKE = "❤️ لایک"
BTN_LIKED = "💕 لایک شده"
BTN_ADD = "➕ اضافه کن"
BTN_PLAY = "▶️ پلی"
BTN_SHARE = "📤 شیر کن"

BTN_FOLLOW = "➕ فالو"
BTN_UNFOLLOW = "➖ آنفالو"
BTN_FOLLOWING = "✅ فالو میکنی"

BTN_DELETE = "🗑️ حذف"
BTN_EDIT = "✏️ ویرایش"
BTN_BACK = "🔙 برگشت"
BTN_CANCEL = "❌ لغو"

# ===== CONFIRMATION =====
CONFIRM_DELETE = "مطمئنی میخوای پاکش کنی؟ 🤔"
CONFIRM_YES = "آره، پاکش کن"
CONFIRM_NO = "نه، ولش کن"

# ===== MISC =====
LOADING = "یه لحظه صبر کن... ⏳"
DONE = "تموم شد! ✅"
SUCCESS = "باحال شد! 🔥"
CANCELLED = "لغو شد ✅"