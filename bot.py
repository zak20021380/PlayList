# bot.py - Main Bot File
# فایل اصلی ربات

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)
from telegram.constants import ParseMode
import asyncio

from config import *
from database import db
from utils import *
from texts import *
from admin import (
    GIVE_PREMIUM_ID,
    GIVE_PREMIUM_DAYS,
    ADD_PLAN_TITLE,
    ADD_PLAN_PRICE,
    ADD_PLAN_DURATION,
    EDIT_PLAN_PRICE,
    EDIT_PLAN_DURATION,
    admin_premium,
    admin_premium_list,
    admin_give_premium_start,
    admin_give_premium_id,
    admin_give_premium_days,
    admin_add_plan_start,
    admin_add_plan_title,
    admin_add_plan_price,
    admin_add_plan_duration,
    admin_edit_plan_menu,
    admin_plan_price_start,
    admin_plan_price_value,
    admin_plan_duration_start,
    admin_plan_duration_value,
    admin_plan_delete_start,
    admin_plan_delete_confirm,
)

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
PLAYLIST_NAME, PLAYLIST_MOOD = range(2)


# ===== HELPER FUNCTIONS =====

def get_main_keyboard():
    """Main menu keyboard"""
    keyboard = [
        [BTN_MY_PLAYLISTS, BTN_BROWSE],
        [BTN_TRENDING, BTN_PROFILE],
        [BTN_LEADERBOARD, BTN_PREMIUM],
        [BTN_HELP, BTN_SETTINGS],
    ]
    return keyboard


async def send_response(
    update: Update,
    text: str,
    *,
    reply_markup=None,
    parse_mode: str = ParseMode.MARKDOWN,
):
    """Send a message or edit existing one based on update type"""
    message = update.effective_message

    if update.callback_query:
        await message.edit_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    else:
        await message.reply_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )


async def send_notification(user_id: int, message: str, context: ContextTypes.DEFAULT_TYPE):
    """Send notification to user"""
    if should_send_notification(user_id, db):
        try:
            await context.bot.send_message(chat_id=user_id, text=message, parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(NOTIFICATION_DELAY)
        except Exception as e:
            logger.error(f"Failed to send notification to {user_id}: {e}")


# ===== COMMAND HANDLERS =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user = update.effective_user

    # Check if banned
    if db.is_banned(user.id):
        await update.message.reply_text(ERROR_USER_BANNED)
        return

    # Create or get user
    db_user = db.get_user(user.id)
    if not db_user:
        db.create_user(user.id, user.username, user.first_name)

    # Send welcome message
    await update.message.reply_text(
        WELCOME,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup={"keyboard": get_main_keyboard(), "resize_keyboard": True}
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    await update.message.reply_text(HELP, parse_mode=ParseMode.MARKDOWN)


async def new_playlist_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start creating new playlist"""
    user_id = update.effective_user.id

    if db.is_banned(user_id):
        await update.message.reply_text(ERROR_USER_BANNED)
        return ConversationHandler.END

    # Check playlist limit
    user = db.get_user(user_id)
    is_premium = db.is_premium(user_id)
    limit = PREMIUM_PLAYLIST_LIMIT if is_premium else FREE_PLAYLIST_LIMIT

    if limit and limit > 0 and len(user['playlists']) >= limit:
        await update.message.reply_text(
            PLAYLIST_LIMIT_REACHED.format(limit=limit),
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    await update.message.reply_text(NEW_PLAYLIST_START)
    return PLAYLIST_NAME


async def new_playlist_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive playlist name"""
    name = update.message.text

    if not is_valid_playlist_name(name):
        await update.message.reply_text("اسم پلی‌لیست باید بین 2 تا 100 کاراکتر باشه! دوباره بنویس:")
        return PLAYLIST_NAME

    context.user_data['playlist_name'] = name

    # Ask for mood
    await update.message.reply_text(
        NEW_PLAYLIST_MOOD,
        reply_markup=create_mood_keyboard()
    )
    return PLAYLIST_MOOD


async def new_playlist_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive playlist mood"""
    query = update.callback_query
    await query.answer()

    mood = query.data.replace('mood_', '')
    playlist_name = context.user_data.get('playlist_name')

    # Create playlist
    playlist_id = db.create_playlist(
        update.effective_user.id,
        playlist_name,
        mood
    )

    if playlist_id:
        playlist = db.get_playlist(playlist_id)
        is_premium = db.is_premium(update.effective_user.id)
        playlist_name_md = escape_markdown(playlist_name)
        base_message = PLAYLIST_CREATED.format(name=playlist_name_md)

        if playlist:
            max_songs = playlist.get('max_songs', FREE_SONGS_PER_PLAYLIST)
        else:
            max_songs = FREE_SONGS_PER_PLAYLIST

        if is_premium:
            message = (
                base_message
                + "\n\n"
                + "فقط فایل صوتی بفرست؛ اگه اسم پلی‌لیست رو تو کپشن هم بنویسی سریع‌تر می‌فهمم!"
                + f"\nبا {MIN_SONGS_TO_PUBLISH} آهنگ منتشر میشه و بعدش هرچقدر خواستی آهنگ اضافه کن!"
            )
        else:
            message = (
                f"{base_message}\n"
                + PLAYLIST_CREATED_FREE.format(max_songs=max_songs)
                + "\n\nفقط فایل صوتی بفرست؛ اگر اسم پلی‌لیست رو تو کپشن بنویسی کارم راحت‌تر میشه."
                + f"\nبعد از {MIN_SONGS_TO_PUBLISH} آهنگ منتشر میشه و ظرفیتش تکمیل میشه."
            )

        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await query.edit_message_text(ERROR_GENERAL)

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    await update.message.reply_text(CANCELLED)
    return ConversationHandler.END


async def my_playlists(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's playlists"""
    user_id = update.effective_user.id
    playlists = db.get_user_playlists(user_id)

    if not playlists:
        await send_response(update, NO_PLAYLISTS, parse_mode=None)
        return

    message = "🎵 **پلی‌لیست‌های من:**\n\n"
    buttons = []
    is_premium = db.is_premium(user_id)

    for pl in playlists:
        mood = DEFAULT_MOODS.get(pl['mood'], '🎵')
        songs_count = len(pl.get('songs', []))
        likes_count = len(pl.get('likes', []))
        name = escape_markdown(pl['name'])
        status = pl.get('status', 'published')
        status_icon = '✅' if status == 'published' else '📝'
        status_text = 'منتشر شده' if status == 'published' else 'پیش‌نویس'
        max_songs = pl.get('max_songs', 0) or 0

        if max_songs and max_songs < PREMIUM_SONGS_PER_PLAYLIST:
            count_display = f"{songs_count}/{max_songs}"
        elif max_songs and max_songs >= PREMIUM_SONGS_PER_PLAYLIST:
            count_display = f"{songs_count}/∞"
        elif is_premium:
            count_display = f"{songs_count}/∞"
        else:
            count_display = str(songs_count)

        message += f"{status_icon} {mood} **{name}** — {status_text}\n"
        message += f"   🎧 {count_display} | ❤️ {likes_count} لایک\n"

        if status != 'published':
            remaining = max(MIN_SONGS_TO_PUBLISH - songs_count, 0)
            if remaining > 0:
                message += f"   ⏳ هنوز {remaining} آهنگ دیگه لازمه تا منتشر بشه\n"

        message += "\n"

        buttons.append([
            InlineKeyboardButton(
                f"▶️ {pl['name']}",
                callback_data=f"play_{pl['id']}"
            ),
            InlineKeyboardButton(
                "🗑️",
                callback_data=f"delete_{pl['id']}"
            )
        ])

    await send_response(
        update,
        message,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def browse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Browse all playlists"""
    keyboard = [
        [InlineKeyboardButton("🔥 ترند", callback_data="browse_trending")],
        [InlineKeyboardButton("✨ جدیدترین‌ها", callback_data="browse_new")],
        [InlineKeyboardButton("👑 برترین‌ها", callback_data="browse_top")],
        [InlineKeyboardButton("🔍 جستجو", callback_data="browse_search")],
    ]

    # Add mood categories
    mood_buttons = []
    for mood_key, mood_name in DEFAULT_MOODS.items():
        mood_buttons.append(
            InlineKeyboardButton(mood_name, callback_data=f"browse_mood_{mood_key}")
        )

    # Split into rows of 2
    for i in range(0, len(mood_buttons), 2):
        keyboard.append(mood_buttons[i:i + 2])

    await send_response(
        update,
        BROWSE_MENU,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show trending playlists"""
    playlists = db.get_trending_playlists(limit=20)

    if not playlists:
        await send_response(
            update,
            "هنوز پلی‌لیست ترندی نیست! اولین نفر باش! 🚀",
            parse_mode=None,
        )
        return

    message = TRENDING_HEADER
    buttons = []

    for i, pl in enumerate(playlists[:10], 1):
        rank_emoji = get_rank_emoji(i)
        name = escape_markdown(pl['name'])
        owner = escape_markdown(pl['owner_name'])
        message += f"{rank_emoji} **{name}** by {owner}\n"
        message += f"   ▶️ {pl.get('plays', 0)} | ❤️ {len(pl.get('likes', []))}\n\n"

        buttons.append([
            InlineKeyboardButton(
                f"{rank_emoji} {pl['name']}",
                callback_data=f"play_{pl['id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("🔙 بازگشت", callback_data="browse_menu")
    ])

    await send_response(
        update,
        message,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def new_playlists(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show newest playlists"""
    playlists = db.get_new_playlists(limit=20)

    if not playlists:
        await send_response(
            update,
            "فعلاً پلی‌لیست تازه‌ای ساخته نشده! 🎧",
            parse_mode=None,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="browse_menu")]
            ]),
        )
        return

    message = NEW_PLAYLISTS_HEADER
    buttons = []

    for pl in playlists[:10]:
        mood = DEFAULT_MOODS.get(pl.get('mood'), '🎵')
        name = escape_markdown(pl['name'])
        owner = escape_markdown(pl['owner_name'])
        created = format_date(pl.get('created_at', ''))
        message += f"{mood} **{name}** by {owner}\n"
        message += (
            f"   ❤️ {len(pl.get('likes', []))} | ▶️ {pl.get('plays', 0)} | 📅 {created}\n\n"
        )

        buttons.append([
            InlineKeyboardButton(
                f"▶️ {pl['name']}",
                callback_data=f"play_{pl['id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("🔙 بازگشت", callback_data="browse_menu")
    ])

    await send_response(
        update,
        message,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def top_playlists(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top playlists by likes"""
    playlists = db.get_top_playlists(limit=20)

    if not playlists:
        await send_response(
            update,
            "هنوز پلی‌لیست محبوبی وجود نداره!",
            parse_mode=None,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="browse_menu")]
            ]),
        )
        return

    message = TOP_PLAYLISTS_HEADER
    buttons = []

    for i, pl in enumerate(playlists[:10], 1):
        medal = get_rank_emoji(i)
        name = escape_markdown(pl['name'])
        owner = escape_markdown(pl['owner_name'])
        likes = len(pl.get('likes', []))
        plays = pl.get('plays', 0)
        message += f"{medal} **{name}** by {owner}\n"
        message += f"   ❤️ {likes} | ▶️ {plays}\n\n"

        buttons.append([
            InlineKeyboardButton(
                f"{medal} {pl['name']}",
                callback_data=f"play_{pl['id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("🔙 بازگشت", callback_data="browse_menu")
    ])

    await send_response(
        update,
        message,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def mood_playlists(update: Update, context: ContextTypes.DEFAULT_TYPE, mood_key: str):
    """Show playlists filtered by mood"""
    playlists = db.get_playlists_by_mood(mood_key, limit=20)
    mood_name = DEFAULT_MOODS.get(mood_key, mood_key)

    if not playlists:
        await send_response(
            update,
            f"برای حال‌وهوای {mood_name} هنوز پلی‌لیستی نداریم!",
            parse_mode=None,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="browse_menu")]
            ]),
        )
        return

    message = f"{mood_name} **پلی‌لیست‌های این حال‌وهوا:**\n\n"
    buttons = []

    for pl in playlists[:10]:
        name = escape_markdown(pl['name'])
        owner = escape_markdown(pl['owner_name'])
        likes = len(pl.get('likes', []))
        plays = pl.get('plays', 0)
        message += f"{mood_name} **{name}** by {owner}\n"
        message += f"   ❤️ {likes} | ▶️ {plays}\n\n"

        buttons.append([
            InlineKeyboardButton(
                f"▶️ {pl['name']}",
                callback_data=f"play_{pl['id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("🔙 بازگشت", callback_data="browse_menu")
    ])

    await send_response(
        update,
        message,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def show_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """Send playlist search results"""
    playlists = db.search_playlists(query)

    if not playlists:
        await update.message.reply_text(
            SEARCH_NO_RESULTS,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 جستجوی دوباره", callback_data="browse_search")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="browse_menu")],
            ])
        )
        return

    text = f"🔍 **نتایج برای:** {escape_markdown(query)}\n\n"
    buttons = []

    for pl in playlists[:10]:
        mood = DEFAULT_MOODS.get(pl.get('mood'), '🎵')
        name = escape_markdown(pl['name'])
        owner = escape_markdown(pl['owner_name'])
        likes = len(pl.get('likes', []))
        plays = pl.get('plays', 0)

        text += f"{mood} **{name}** by {owner}\n"
        text += f"   ❤️ {likes} | ▶️ {plays}\n\n"

        buttons.append([
            InlineKeyboardButton(
                f"▶️ {pl['name']}",
                callback_data=f"play_{pl['id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("🔁 جستجوی دوباره", callback_data="browse_search")
    ])
    buttons.append([
        InlineKeyboardButton("🔙 بازگشت", callback_data="browse_menu")
    ])

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user profile"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text(ERROR_GENERAL)
        return

    playlists = db.get_user_playlists(user_id)
    total_songs = sum(len(pl['songs']) for pl in playlists)
    rank = db.get_user_rank(user_id)

    status = "💎 پریمیوم" if db.is_premium(user_id) else "🆓 رایگان"
    badges_text = format_badges(user.get('badges', []))

    profile_text = PROFILE_TEXT.format(
        name=user['first_name'],
        playlists_count=len(playlists),
        songs_count=total_songs,
        likes_received=user.get('total_likes_received', 0),
        plays_received=user.get('total_plays', 0),
        followers=len(user.get('followers', [])),
        following=len(user.get('following', [])),
        rank=rank if rank else "نامشخص",
        badges=badges_text,
        status=status,
        join_date=format_date(user['join_date'])
    )

    buttons = [
        [InlineKeyboardButton("🎵 پلی‌لیست‌هام", callback_data="my_playlists")],
        [InlineKeyboardButton("📊 آمار کامل", callback_data="my_stats")],
    ]

    if not db.is_premium(user_id):
        buttons.append([InlineKeyboardButton("💎 پریمیوم بگیر", callback_data="premium")])

    await update.message.reply_text(
        profile_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show leaderboard"""
    user_id = update.effective_user.id
    leaderboard_entries = db.get_leaderboard(sort_by='likes', limit=0)
    top_users = leaderboard_entries[:20]
    total_users = len(leaderboard_entries)

    user_entry = None
    user_rank = 0
    user_id_str = str(user_id)

    for index, entry in enumerate(leaderboard_entries, 1):
        if entry['user_id'] == user_id_str:
            user_entry = entry
            user_rank = index
            break

    message = LEADERBOARD_HEADER.format(period="این هفته")

    for i, user in enumerate(top_users, 1):
        rank_emoji = get_rank_emoji(i)
        premium_badge = " 💎" if user['is_premium'] else ""

        message += LEADERBOARD_ITEM.format(
            rank=rank_emoji,
            name=escape_markdown(user['name']),
            premium=premium_badge,
            likes=format_number(user['likes']),
            plays=format_number(user['plays']),
            songs=format_number(user['songs']),
            playlists=format_number(user['playlists']),
            score=format_number(user['score'])
        )

    if user_entry and user_rank:
        message += LEADERBOARD_YOUR_RANK.format(
            rank=user_rank,
            total=total_users,
            likes=format_number(user_entry['likes']),
            plays=format_number(user_entry['plays']),
            songs=format_number(user_entry['songs']),
            score=format_number(user_entry['score'])
        )

    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


async def premium_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show premium info"""
    user_id = update.effective_user.id

    if db.is_premium(user_id):
        user = db.get_user(user_id)
        expiry_date = format_date(user['premium_until'])
        await update.message.reply_text(
            ALREADY_PREMIUM.format(date=expiry_date),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Show premium info
    plans = db.get_premium_plans()

    if plans:
        plan_lines = "\n".join(
            [
                f"• {escape_markdown(plan['title'])}: {format_number(plan['price'])} تومان / {plan['duration_days']} روز"
                for plan in plans
            ]
        )
    else:
        plan_lines = "به زودی پلن‌های جدید اضافه میشه!"

    info_text = PREMIUM_INFO.format(plans=plan_lines)

    buttons = [
        [
            InlineKeyboardButton(
                f"{plan['title']} — {format_number(plan['price'])} تومان",
                callback_data=f"buy_plan_{plan['id']}"
            )
        ]
        for plan in plans
    ] or [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]

    await update.message.reply_text(
        info_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ===== AUDIO HANDLER =====

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle audio file upload"""
    user_id = update.effective_user.id

    if db.is_banned(user_id):
        await update.message.reply_text(ERROR_USER_BANNED)
        return

    # Check if it's audio
    if not update.message.audio:
        await update.message.reply_text(ERROR_NO_AUDIO)
        return

    # Determine target playlist
    caption = update.message.caption
    user_playlists = db.get_user_playlists(user_id)
    playlist = None

    if caption:
        for pl in user_playlists:
            if pl['name'].lower() == caption.lower():
                playlist = pl
                break

    if not playlist:
        playlist = db.get_active_playlist(user_id)

    if not playlist:
        if not user_playlists:
            await update.message.reply_text(
                UPLOAD_NO_PLAYLIST.format(playlists="هنوز پلی‌لیستی نساختی!")
            )
        else:
            playlists_list = "پلی‌لیست‌های تو:\n" + "\n".join([f"• {pl['name']}" for pl in user_playlists])
            await update.message.reply_text(
                UPLOAD_NO_PLAYLIST.format(playlists=playlists_list)
            )
        return

    max_songs = playlist.get('max_songs', 0) or 0
    current_count = len(playlist.get('songs', []))
    if max_songs and current_count >= max_songs:
        await update.message.reply_text(
            PLAYLIST_FULL.format(max_songs=max_songs),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Store audio in storage channel
    try:
        forwarded = await context.bot.forward_message(
            chat_id=STORAGE_CHANNEL_ID,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
        )
    except Exception as exc:
        logger.error(f"Failed to forward audio to storage channel: {exc}")
        await update.message.reply_text(ERROR_GENERAL)
        return

    # Get audio info
    audio = update.message.audio
    song_data = {
        'title': audio.title or 'Unknown',
        'performer': audio.performer or 'Unknown',
        'duration': audio.duration or 0,
        'file_size': audio.file_size or 0,
        'channel_message_id': forwarded.message_id,
        'storage_channel_id': STORAGE_CHANNEL_ID,
    }

    success, status = db.add_song_to_playlist(playlist['id'], song_data)

    if success:
        db.set_active_playlist(user_id, playlist['id'])

    if not success:
        if status == 'playlist_full':
            await update.message.reply_text(
                PLAYLIST_FULL.format(max_songs=playlist.get('max_songs', 0)),
                parse_mode=ParseMode.MARKDOWN,
            )
        elif status == 'storage_missing':
            await update.message.reply_text(ERROR_GENERAL)
        else:
            await update.message.reply_text(ERROR_GENERAL)
        return

    updated_playlist = db.get_playlist(playlist['id'])
    updated_count = len(updated_playlist.get('songs', []))

    if status == 'playlist_published':
        await update.message.reply_text(
            PLAYLIST_PUBLISHED,
            parse_mode=ParseMode.MARKDOWN,
        )
    elif status == 'draft_progress':
        remaining = max(MIN_SONGS_TO_PUBLISH - updated_count, 0)
        await update.message.reply_text(
            PLAYLIST_DRAFT_PROGRESS.format(
                current=updated_count,
                minimum=MIN_SONGS_TO_PUBLISH,
                remaining=remaining,
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text(
            UPLOAD_SUCCESS.format(playlist=updated_playlist['name']),
            parse_mode=ParseMode.MARKDOWN,
        )


# ===== CALLBACK HANDLERS =====




async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = update.effective_user.id

    # Browse menus
    if data == 'browse_menu':
        context.user_data.pop('awaiting_search', None)
        await browse(update, context)

    elif data == 'browse_trending':
        await trending(update, context)

    elif data == 'browse_new':
        await new_playlists(update, context)

    elif data == 'browse_top':
        await top_playlists(update, context)

    elif data.startswith('browse_mood_'):
        mood_key = data.replace('browse_mood_', '')
        await mood_playlists(update, context, mood_key)

    elif data == 'browse_search':
        context.user_data['awaiting_search'] = True
        await send_response(
            update,
            SEARCH_PROMPT,
            parse_mode=None,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="browse_menu")]
            ]),
        )

    # Like playlist
    elif data.startswith('like_'):
        playlist_id = data.replace('like_', '')
        playlist = db.get_playlist(playlist_id)

        if not playlist:
            await query.edit_message_text(ERROR_NOT_FOUND)
            return

        if playlist.get('status') != 'published' and playlist.get('owner_id') != str(user_id):
            await query.answer("این پلی‌لیست هنوز منتشر نشده!")
            return

        # Check if already liked
        if str(user_id) in playlist.get('likes', []):
            # Unlike
            db.unlike_playlist(user_id, playlist_id)
            await query.answer(UNLIKED)
        else:
            # Like
            if db.like_playlist(user_id, playlist_id):
                await query.answer(LIKED)

                # Send notification to owner
                owner_id = int(playlist['owner_id'])
                if owner_id != user_id:
                    user = db.get_user(user_id)
                    notif_text = NOTIF_LIKED.format(
                        user=user['first_name'],
                        playlist=playlist['name']
                    )
                    await send_notification(owner_id, notif_text, context)
            else:
                await query.answer(ALREADY_LIKED)

    # Add to playlist
    elif data.startswith('add_'):
        playlist_id = data.replace('add_', '')
        playlist = db.get_playlist(playlist_id)

        if not playlist or (playlist.get('status') != 'published' and playlist.get('owner_id') != str(user_id)):
            await query.answer("این پلی‌لیست هنوز منتشر نشده!")
            return

        context.user_data['adding_from'] = playlist_id

        # Show user's playlists
        user_playlists = db.get_user_playlists(user_id)
        if not user_playlists:
            await query.answer("اول یه پلی‌لیست بساز!")
            return

        buttons = []
        for pl in user_playlists:
            buttons.append([
                InlineKeyboardButton(
                    pl['name'],
                    callback_data=f"addto_{pl['id']}"
                )
            ])

        await query.edit_message_text(
            CHOOSE_PLAYLIST_TO_ADD,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # Play playlist
    elif data.startswith('play_'):
        playlist_id = data.replace('play_', '')
        playlist = db.get_playlist(playlist_id)

        if not playlist:
            await query.answer("این پلی‌لیست پیدا نشد!")
            return

        if playlist.get('status') != 'published' and playlist.get('owner_id') != str(user_id):
            await query.answer("این پلی‌لیست هنوز منتشر نشده!")
            return

        if not playlist['songs']:
            await query.answer("این پلی‌لیست خالیه!")

        # Send playlist info before songs
        mood_label = DEFAULT_MOODS.get(playlist.get('mood', 'happy'), playlist.get('mood', 'نامشخص'))
        songs_info_lines = []

        for index, song_id in enumerate(playlist['songs'], 1):
            song = db.data['songs'].get(song_id)
            if not song:
                continue

            title = song.get('title') or 'بدون عنوان'
            performer = song.get('performer') or ''
            duration = format_duration(song.get('duration', 0))

            title_md = escape_markdown(str(title))
            performer_md = escape_markdown(str(performer)) if performer and performer.lower() != 'unknown' else ''

            if performer_md:
                songs_info_lines.append(f"{index}. {title_md} — {performer_md} ({duration})")
            else:
                songs_info_lines.append(f"{index}. {title_md} ({duration})")

        if songs_info_lines:
            songs_text = "\n".join(songs_info_lines)
        else:
            songs_text = "هیچ آهنگی برای نمایش موجود نیست."

        playlist_summary = (
            f"🎧 **{escape_markdown(playlist['name'])}**\n"
            f"📂 دسته‌بندی: {escape_markdown(mood_label)}\n"
            f"🎵 تعداد آهنگ‌ها: {len(playlist['songs'])}\n\n"
            f"{songs_text}"
        )

        await context.bot.send_message(
            chat_id=user_id,
            text=playlist_summary,
            parse_mode=ParseMode.MARKDOWN,
        )

        if playlist['songs']:
            # Increment plays
            db.increment_plays(playlist_id)

            # Send all songs
            await query.answer(f"در حال پخش {playlist['name']}...")

            for song_id in playlist['songs']:
                song = db.data['songs'].get(song_id)
                if song:
                    caption = get_song_info(song)
                    try:
                        channel_message_id = song.get('channel_message_id')
                        storage_channel_id = song.get('storage_channel_id', STORAGE_CHANNEL_ID)
                        if channel_message_id and storage_channel_id:
                            await context.bot.copy_message(
                                chat_id=user_id,
                                from_chat_id=storage_channel_id,
                                message_id=channel_message_id,
                                caption=caption,
                                parse_mode=ParseMode.MARKDOWN,
                                reply_markup=create_song_buttons(song_id, playlist_id),
                            )
                        elif song.get('file_id'):
                            await context.bot.send_audio(
                                chat_id=user_id,
                                audio=song['file_id'],
                                caption=caption,
                                parse_mode=ParseMode.MARKDOWN,
                                reply_markup=create_song_buttons(song_id, playlist_id)
                            )
                        else:
                            raise ValueError('Missing song storage reference')
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        logger.error(f"Failed to send audio: {e}")

    # User quick actions
    elif data == 'my_playlists':
        await my_playlists(update, context)

    elif data == 'premium':
        await premium_info(update, context)

    # Delete playlist
    elif data.startswith('delete_'):
        playlist_id = data.replace('delete_', '')
        playlist = db.get_playlist(playlist_id)

        if playlist and playlist['owner_id'] == str(user_id):
            # Confirm
            buttons = [
                [InlineKeyboardButton(CONFIRM_YES, callback_data=f"confirm_delete_{playlist_id}")],
                [InlineKeyboardButton(CONFIRM_NO, callback_data="cancel_delete")],
            ]
            await query.edit_message_text(
                CONFIRM_DELETE,
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    # Confirm delete
    elif data.startswith('confirm_delete_'):
        playlist_id = data.replace('confirm_delete_', '')
        db.delete_playlist(playlist_id)
        await query.edit_message_text(PLAYLIST_DELETED)

    # Cancel delete
    elif data == 'cancel_delete':
        await query.edit_message_text(CANCELLED)

        # Toggle notifications
    elif data == 'toggle_notif':
        user = db.get_user(user_id)
        current = user.get('notifications_enabled', True)
        db.update_user(user_id, {'notifications_enabled': not current})

        status = "خاموش" if current else "روشن"
        await query.answer(f"نوتیفیکیشن‌ها {status} شد!")

        # Refresh settings menu
        notif_status = "✅ فعال" if not current else "❌ غیرفعال"
        message = f"""
    ⚙️ **تنظیمات**

    🔔 نوتیفیکیشن‌ها: {notif_status}

    از دکمه‌های زیر استفاده کن:
    """
        buttons = [
            [InlineKeyboardButton(
                "🔔 نوتیفیکیشن‌ها روشن/خاموش",
                callback_data="toggle_notif"
            )],
            [InlineKeyboardButton("🔙 برگشت", callback_data="back_main")],
        ]
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # Back to main
    elif data == 'back_main':
        await query.message.delete()

    # Buy premium
    elif data == 'buy_premium':
        plans = db.get_premium_plans()

        if not plans:
            await query.edit_message_text("فعلاً هیچ پلنی تعریف نشده!")
            return

        buttons = [
            [
                InlineKeyboardButton(
                    f"{plan['title']} — {format_number(plan['price'])} تومان",
                    callback_data=f"buy_plan_{plan['id']}"
                )
            ]
            for plan in plans
        ]

        await query.edit_message_text(
            "یکی از پلن‌های زیر رو انتخاب کن:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith('buy_plan_'):
        plan_id = data.replace('buy_plan_', '')
        plan = db.get_premium_plan(plan_id)

        if not plan:
            await query.answer("پلن پیدا نشد!")
            return

        payment_url = zarinpal.create_payment(
            amount=plan['price'],
            description=f"خرید {plan['title']} پلی‌لیست - {user_id}",
            user_id=user_id
        )

        if payment_url:
            buttons = [
                [InlineKeyboardButton("💳 پرداخت", url=payment_url)],
                [InlineKeyboardButton("🔙 پلن‌های دیگر", callback_data="buy_premium")],
            ]
            await query.edit_message_text(
                PREMIUM_PAYMENT_INSTRUCTIONS.format(
                    title=plan['title'],
                    price=plan['price'],
                    days=plan['duration_days'],
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await query.edit_message_text("مشکلی در ایجاد لینک پرداخت پیش اومد! لطفاً بعداً تلاش کن.")


# ===== ADMIN HANDLERS =====

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    buttons = [
        [InlineKeyboardButton("📊 آمار", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_users")],
        [InlineKeyboardButton("💎 پریمیوم‌ها", callback_data="admin_premium")],
        [InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="admin_settings")],
    ]

    await update.message.reply_text(
        ADMIN_PANEL,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def admin_stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin stats"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    stats = db.get_global_stats()
    stats_text = format_admin_stats(stats)

    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)


# ===== MAIN =====


# ===== MAIN MENU BUTTON HANDLERS =====

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu button presses"""
    text = update.message.text

    if context.user_data.get('awaiting_search'):
        query = text.strip()

        if not query:
            await update.message.reply_text("لطفاً متن جستجو رو بنویس!", parse_mode=None)
            return

        context.user_data.pop('awaiting_search', None)
        await show_search_results(update, context, query)
        return

    if text == BTN_MY_PLAYLISTS or "پلی‌لیست‌های من" in text:
        await my_playlists(update, context)

    elif text == BTN_BROWSE or "مرور" in text:
        await browse(update, context)

    elif text == BTN_TRENDING or "ترند" in text:
        await trending(update, context)

    elif text == BTN_PROFILE or "پروفایل" in text:
        await profile(update, context)

    elif text == BTN_LEADERBOARD or "رتبه‌بندی" in text:
        await leaderboard(update, context)

    elif text == BTN_PREMIUM or "پریمیوم" in text:
        await premium_info(update, context)

    elif text == BTN_HELP or "راهنما" in text:
        await help_command(update, context)

    elif text == BTN_SETTINGS or "تنظیمات" in text:
        await settings(update, context)


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Settings menu"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    notif_status = "✅ فعال" if user.get('notifications_enabled', True) else "❌ غیرفعال"

    message = f"""
⚙️ **تنظیمات**

🔔 نوتیفیکیشن‌ها: {notif_status}

از دکمه‌های زیر استفاده کن:
"""

    buttons = [
        [InlineKeyboardButton(
            "🔔 نوتیفیکیشن‌ها روشن/خاموش",
            callback_data="toggle_notif"
        )],
        [InlineKeyboardButton("🔙 برگشت", callback_data="back_main")],
    ]

    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons)
    )







def main():
    """Start the bot"""
    # Check token
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Error: BOT_TOKEN not set in config.py!")
        print("Get your token from @BotFather and update config.py")
        return

    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myplaylists", my_playlists))
    application.add_handler(CommandHandler("browse", browse))
    application.add_handler(CommandHandler("trending", trending))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("premium", premium_info))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("stats", admin_stats_cmd))

    # New playlist conversation
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('newplaylist', new_playlist_start)],
        states={
            PLAYLIST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_playlist_name)],
            PLAYLIST_MOOD: [CallbackQueryHandler(new_playlist_mood, pattern='^mood_')],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    application.add_handler(conv_handler)

    # Admin premium conversations
    admin_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_give_premium_start, pattern='^admin_give_premium$'),
            CallbackQueryHandler(admin_add_plan_start, pattern='^admin_add_plan$'),
            CallbackQueryHandler(admin_plan_price_start, pattern='^admin_plan_price_'),
            CallbackQueryHandler(admin_plan_duration_start, pattern='^admin_plan_duration_'),
        ],
        states={
            GIVE_PREMIUM_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_give_premium_id)],
            GIVE_PREMIUM_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_give_premium_days)],
            ADD_PLAN_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_plan_title)],
            ADD_PLAN_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_plan_price)],
            ADD_PLAN_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_plan_duration)],
            EDIT_PLAN_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_plan_price_value)],
            EDIT_PLAN_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_plan_duration_value)],
        },
        fallbacks=[CallbackQueryHandler(admin_premium, pattern='^admin_premium$')],
    )
    application.add_handler(admin_conv_handler)

    # Admin premium callbacks
    application.add_handler(CallbackQueryHandler(admin_premium, pattern='^admin_premium$'))
    application.add_handler(CallbackQueryHandler(admin_premium_list, pattern='^admin_premium_list$'))
    application.add_handler(CallbackQueryHandler(admin_edit_plan_menu, pattern='^admin_edit_plan_'))
    application.add_handler(CallbackQueryHandler(admin_plan_delete_start, pattern='^admin_plan_delete_.+$'))
    application.add_handler(CallbackQueryHandler(admin_plan_delete_confirm, pattern='^admin_plan_delete_confirm_.+$'))

    # Audio handler
    application.add_handler(MessageHandler(filters.AUDIO, handle_audio))

    # Callback handlers
    application.add_handler(CallbackQueryHandler(button_callback))

    # Main menu button handler (MUST be last!)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_main_menu
    ))

    # Start bot
    print("🎵 پلی‌لیست ربات راه‌اندازی شد! 🚀")
    print(f"📍 ربات: {BOT_NAME}")
    print(f"👨‍💼 ادمین‌ها: {ADMIN_IDS}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()