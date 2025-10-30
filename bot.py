# bot.py - Main Bot File
# فایل اصلی ربات

import logging
from datetime import datetime, time as datetime_time
from typing import Optional

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
from telegram.error import BadRequest
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
    admin_stats_callback,
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


def _get_support_contact():
    """Return formatted support handle and direct link"""
    username = (SUPPORT_USERNAME or "").strip()
    username = username.lstrip('@')

    if not username:
        username = "support_bot"

    handle = f"@{username}"
    link = f"https://t.me/{username}"
    return handle, link


HELP_SECTION_CONTENT = {
    "overview": HELP,
    "quick_start": HELP_QUICK_START,
    "playlist": HELP_PLAYLIST_MANAGEMENT,
    "interactions": HELP_INTERACTIONS,
    "premium": HELP_PREMIUM,
    "faq": HELP_FAQ,
    "support": HELP_SUPPORT,
}


HELP_SECTION_BUTTONS = [
    ("quick_start", HELP_BTN_QUICK_START),
    ("playlist", HELP_BTN_PLAYLIST),
    ("interactions", HELP_BTN_INTERACTIONS),
    ("premium", HELP_BTN_PREMIUM),
    ("faq", HELP_BTN_FAQ),
    ("support", HELP_BTN_SUPPORT),
]


def build_help_keyboard(section: str, support_link: str) -> InlineKeyboardMarkup:
    """Create inline keyboard for help center"""
    rows = []

    if section != "overview":
        rows.append([
            InlineKeyboardButton(
                HELP_BTN_OVERVIEW,
                callback_data="help_section:overview",
            )
        ])

    for index in range(0, len(HELP_SECTION_BUTTONS), 2):
        row = [
            InlineKeyboardButton(label, callback_data=f"help_section:{key}")
            for key, label in HELP_SECTION_BUTTONS[index:index + 2]
        ]
        if row:
            rows.append(row)

    rows.append([
        InlineKeyboardButton(
            HELP_BTN_CONTACT_SUPPORT,
            url=support_link,
        )
    ])

    return InlineKeyboardMarkup(rows)


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE, section: str = "overview"):
    """Render the help center with the requested section"""
    support_handle, support_link = _get_support_contact()
    support_handle_md = f"[{support_handle}]({support_link})"

    free_limit = "∞" if not FREE_PLAYLIST_LIMIT else str(FREE_PLAYLIST_LIMIT)
    free_songs = "∞" if not FREE_SONGS_PER_PLAYLIST else str(FREE_SONGS_PER_PLAYLIST)
    premium_limit = "∞" if not PREMIUM_PLAYLIST_LIMIT else str(PREMIUM_PLAYLIST_LIMIT)
    premium_songs = "∞" if not PREMIUM_SONGS_PER_PLAYLIST else str(PREMIUM_SONGS_PER_PLAYLIST)

    template = HELP_SECTION_CONTENT.get(section, HELP_SECTION_CONTENT["overview"])
    message = template.format(
        support_handle=support_handle_md,
        min_songs=MIN_SONGS_TO_PUBLISH,
        free_limit=free_limit,
        free_songs=free_songs,
        premium_limit=premium_limit,
        premium_songs=premium_songs,
        support_link=support_link,
    )

    keyboard = build_help_keyboard(section, support_link)

    await send_response(
        update,
        message,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )


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
        try:
            if message.text:
                await message.edit_text(
                    text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                )
            elif message.caption:
                await message.edit_caption(
                    caption=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                )
            else:
                await message.reply_text(
                    text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                )
        except BadRequest as exc:
            if 'message is not modified' in str(exc).lower():
                return
            if message.caption:
                await message.reply_text(
                    text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                )
            else:
                raise
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


async def send_playlist_details(
    user_id: int,
    playlist: dict,
    context: ContextTypes.DEFAULT_TYPE,
    playlist_id: Optional[str] = None,
):
    """Send playlist summary and songs to a user"""
    playlist_identifier = playlist_id or playlist.get('id')

    mood_label = DEFAULT_MOODS.get(
        playlist.get('mood', 'happy'),
        playlist.get('mood', 'نامشخص'),
    )

    songs_info_lines = []

    for index, song_id in enumerate(playlist.get('songs', []), 1):
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

    songs_text = "\n".join(songs_info_lines) if songs_info_lines else "هیچ آهنگی برای نمایش موجود نیست."

    is_owner = playlist.get('owner_id') == str(user_id)
    max_songs = playlist.get('max_songs', 0) or 0
    current_count = len(playlist.get('songs', []))
    owner_lines = []

    if is_owner:
        current_display = format_number(current_count)
        maximum_display = "∞" if not max_songs else format_number(max_songs)
        owner_lines.append(
            PLAYLIST_CAPACITY_STATUS.format(
                current=current_display,
                maximum=maximum_display,
            )
        )

        if max_songs and current_count >= max_songs:
            owner_lines.append(
                PLAYLIST_OWNER_FULL_HINT.format(
                    current=current_display,
                    maximum=maximum_display,
                )
            )
        else:
            owner_lines.append(PLAYLIST_OWNER_ADD_HINT)

    playlist_summary = (
        f"🎧 **{escape_markdown(playlist['name'])}**\n"
        f"📂 دسته‌بندی: {escape_markdown(mood_label)}\n"
        f"🎵 تعداد آهنگ‌ها: {len(playlist.get('songs', []))}\n\n"
        f"{songs_text}"
    )

    if owner_lines:
        playlist_summary += "\n\n" + "\n".join(owner_lines)

    summary_reply_markup = None
    if is_owner and (not max_songs or current_count < max_songs) and playlist_identifier:
        summary_reply_markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "➕ افزودن آهنگ جدید",
                    callback_data=f"set_active_add:{playlist_identifier}",
                )
            ]
        ])

    await context.bot.send_message(
        chat_id=user_id,
        text=playlist_summary,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=summary_reply_markup,
    )

    if playlist.get('songs') and playlist_identifier:
        db.increment_plays(playlist_identifier)

        for song_id in playlist['songs']:
            song = db.data['songs'].get(song_id)
            if not song:
                continue

            caption = get_song_info(song)
            original_id = song.get('original_song_id', song_id)
            user_liked = str(user_id) in song.get('likes', [])
            already_added = db.user_has_song_copy(user_id, original_id)
            like_count = len(song.get('likes', []))
            add_count = db.count_song_adds(original_id)
            can_remove = is_owner

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
                        reply_markup=create_song_buttons(
                            song_id,
                            playlist_identifier,
                            user_liked=user_liked,
                            already_added=already_added,
                            like_count=like_count,
                            add_count=add_count,
                            can_remove=can_remove,
                        ),
                    )
                elif song.get('file_id'):
                    await context.bot.send_audio(
                        chat_id=user_id,
                        audio=song['file_id'],
                        caption=caption,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=create_song_buttons(
                            song_id,
                            playlist_identifier,
                            user_liked=user_liked,
                            already_added=already_added,
                            like_count=like_count,
                            add_count=add_count,
                            can_remove=can_remove,
                        ),
                    )
                else:
                    raise ValueError('Missing song storage reference')

                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Failed to send audio: {e}")


async def send_daily_top_song(context: ContextTypes.DEFAULT_TYPE):
    """Send the most liked song of the day to all users at 22:00"""
    target_date = datetime.now().strftime('%Y-%m-%d')

    if db.get_last_top_song_broadcast() == target_date:
        return

    song, daily_likes = db.get_top_song_of_day(target_date)

    if not song or daily_likes <= 0:
        return

    song_title = escape_markdown(song.get('title') or 'آهنگ')
    performer = escape_markdown(song.get('performer') or 'نامشخص')
    total_likes = len(song.get('likes', []))
    caption_lines = [
        "🌟 *آهنگ محبوب امروز*",
        "این آهنگ امروز بیشترین طرفدار رو داشت! ❤️",
        "",
        f"🎵 {song_title}",
        f"👤 {performer}",
        f"❤️ لایک‌های امروز: {daily_likes}",
        f"❤️ کل لایک‌ها: {total_likes}",
    ]
    caption = "\n".join(caption_lines)

    song_id = song.get('id') or song.get('original_song_id')
    channel_message_id = song.get('channel_message_id')
    storage_channel_id = song.get('storage_channel_id', STORAGE_CHANNEL_ID)
    original_song_id = song.get('original_song_id', song_id)
    add_count = db.count_song_adds(original_song_id)
    song_likes = set(song.get('likes', []))
    total_song_likes = len(song_likes)

    owner_raw = song.get('uploader_id')
    try:
        owner_id = int(owner_raw) if owner_raw is not None else None
    except (TypeError, ValueError):
        owner_id = None

    recipients = db.data.get('users', {}).values()

    for user in recipients:
        if user.get('banned'):
            continue

        try:
            user_id = int(user['user_id'])
        except (TypeError, ValueError):
            continue

        if owner_id and user_id == owner_id:
            continue

        if not should_send_notification(user_id, db):
            continue

        user_liked = str(user_id) in song_likes
        already_added = db.user_has_song_copy(user_id, original_song_id)

        try:
            if channel_message_id and storage_channel_id:
                await context.bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=storage_channel_id,
                    message_id=channel_message_id,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=create_song_buttons(
                        song_id,
                        'daily_top',
                        user_liked=user_liked,
                        already_added=already_added,
                        like_count=total_song_likes,
                        add_count=add_count,
                    ),
                )
            elif song.get('file_id'):
                await context.bot.send_audio(
                    chat_id=user_id,
                    audio=song['file_id'],
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=create_song_buttons(
                        song_id,
                        'daily_top',
                        user_liked=user_liked,
                        already_added=already_added,
                        like_count=total_song_likes,
                        add_count=add_count,
                    ),
                )
            else:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=caption,
                    parse_mode=ParseMode.MARKDOWN,
                )

            await asyncio.sleep(NOTIFICATION_DELAY)
        except Exception as exc:
            logger.error("Failed to send daily top song to %s: %s", user_id, exc)

    if owner_id:
        owner = db.get_user(owner_id)
        if owner and not owner.get('banned'):
            owner_name = escape_markdown(owner.get('first_name') or 'دوست عزیز')
            owner_message = (
                f"🎉 *تبریک {owner_name}!*\n"
                f"آهنگ «{song_title}» امشب بیشترین لایک رو داشت. ❤️\n"
                f"تعداد لایک‌های امروز: {daily_likes}"
            )

            try:
                await context.bot.send_message(
                    chat_id=owner_id,
                    text=owner_message,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception as exc:
                logger.error("Failed to notify owner %s about daily top song: %s", owner_id, exc)

    db.set_last_top_song_broadcast(target_date)

# ===== COMMAND HANDLERS =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user = update.effective_user
    message = update.effective_message

    # Check if banned
    if db.is_banned(user.id):
        if message:
            await message.reply_text(ERROR_USER_BANNED)
        return

    # Create or get user
    db_user = db.get_user(user.id)
    new_user = False
    if not db_user:
        db_user = db.create_user(user.id, user.username, user.first_name)
        new_user = True

    db.touch_user(user.id)

    args = context.args if context.args else []
    send_welcome = new_user or not args

    if send_welcome and message:
        await message.reply_text(
            WELCOME,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup={"keyboard": get_main_keyboard(), "resize_keyboard": True}
        )

    if args:
        payload = args[0]
        if payload.startswith('pl_'):
            playlist_id = payload
            playlist = db.get_playlist(playlist_id)

            if not playlist:
                if message:
                    await message.reply_text(ERROR_NOT_FOUND)
                return

            if playlist.get('status') != 'published' and playlist.get('owner_id') != str(user.id):
                if message:
                    await message.reply_text(PLAYLIST_NOT_PUBLISHED)
                return

            await send_playlist_details(user.id, playlist, context, playlist_id)
            return


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    await show_help(update, context)


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
        account_type = "پریمیوم" if is_premium else "رایگان"
        extra_hint = (
            "برای ساخت پلی‌لیست جدید باید یکی از پلی‌لیست‌های فعلی رو حذف یا آرشیو کنی."
            if is_premium
            else "برای امکانات بیشتر می‌تونی از منوی /premium پلن مناسب رو انتخاب کنی."
        )
        await update.message.reply_text(
            PLAYLIST_LIMIT_REACHED.format(
                limit=limit,
                account_type=account_type,
                extra_hint=extra_hint,
            ),
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

        if MIN_SONGS_TO_PUBLISH <= 1:
            publish_line = (
                "همین که اولین آهنگ رو بفرستی پلی‌لیست منتشر میشه؛"
                " اما هر وقت خواستی میتونی با /publishplaylist هم منتشرش کنی."
            )
        else:
            publish_line = (
                f"بعد از {MIN_SONGS_TO_PUBLISH} آهنگ خودکار منتشر میشه؛"
                " ولی اگر زودتر آماده بودی با /publishplaylist هم میتونی منتشرش کنی."
            )

        if is_premium:
            message = (
                base_message
                + "\n\n"
                + "فقط فایل صوتی بفرست؛ اگه اسم پلی‌لیست رو تو کپشن هم بنویسی سریع‌تر می‌فهمم!"
                + f"\n{publish_line}\nبه عنوان کاربر پریمیوم می‌تونی تا {max_songs} آهنگ برای هر پلی‌لیست داشته باشی،"
                + " پس بهترین‌ها رو گلچین کن."
            )
        else:
            message = (
                f"{base_message}\n"
                + PLAYLIST_CREATED_FREE.format(max_songs=max_songs)
                + "\n\n"
                + "فقط فایل صوتی بفرست؛ اگر اسم پلی‌لیست رو تو کپشن بنویسی کارم راحت‌تر میشه."
                + f"\n{publish_line}\nظرفیتت تا {max_songs} آهنگ بازه و هر وقت خواستی (حتی با 1 یا 2 آهنگ) با /publishplaylist میتونی پلی‌لیست رو منتشر کنی."
            )

        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await query.edit_message_text(ERROR_GENERAL)

    return ConversationHandler.END


async def publish_playlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Publish the user's active playlist manually"""
    user_id = update.effective_user.id
    playlist = db.get_active_playlist(user_id)

    if not playlist or playlist.get('owner_id') != str(user_id):
        await update.message.reply_text(
            PLAYLIST_PUBLISH_NO_ACTIVE,
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if not playlist.get('songs'):
        await update.message.reply_text(
            PLAYLIST_PUBLISH_NO_SONGS,
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if playlist.get('status') == 'published':
        await update.message.reply_text(
            PLAYLIST_PUBLISH_ALREADY,
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if db.publish_playlist(playlist['id']):
        playlist_name_md = escape_markdown(playlist.get('name', 'پلی‌لیست'))
        await update.message.reply_text(
            PLAYLIST_PUBLISH_SUCCESS.format(name=playlist_name_md),
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text(
            ERROR_GENERAL,
            parse_mode=ParseMode.MARKDOWN,
        )


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
        is_private = pl.get('is_private', False)
        visibility_icon = '🔒' if is_private else '🌐'
        visibility_text = 'مخفی' if is_private else 'عمومی'
        max_songs_raw = pl.get('max_songs')
        if isinstance(max_songs_raw, int):
            if max_songs_raw == 0:
                count_display = f"{songs_count}/∞"
            elif max_songs_raw > 0:
                count_display = f"{songs_count}/{max_songs_raw}"
            else:
                count_display = str(songs_count)
        else:
            count_display = str(songs_count)

        message += f"{status_icon} {mood} **{name}** — {status_text}\n"
        message += f"   🎧 {count_display} | ❤️ {likes_count} لایک\n"
        message += f"   {visibility_icon} وضعیت: {visibility_text}\n"

        if status != 'published':
            remaining = max(MIN_SONGS_TO_PUBLISH - songs_count, 0)
            if remaining > 0:
                message += f"   ⏳ هنوز {remaining} آهنگ دیگه لازمه تا منتشر بشه\n"
            message += "   ✅ هر وقت آماده بودی با /publishplaylist میتونی منتشرش کنی\n"

        message += "\n"

        share_url = build_playlist_share_url(pl['id'], pl['name'])

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

        if share_url:
            buttons.append([
                InlineKeyboardButton(
                    "🔗 اشتراک‌گذاری",
                    callback_data=f"share_{pl['id']}",
                )
            ])

    await send_response(
        update,
        message,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def manage_playlist_visibility(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow user to toggle visibility of their playlists"""
    user_id = update.effective_user.id
    playlists = db.get_user_playlists(user_id)

    if not playlists:
        await send_response(
            update,
            MANAGE_VISIBILITY_EMPTY,
            parse_mode=None,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back_profile")]
            ]),
        )
        return

    message_lines = [MANAGE_VISIBILITY_HEADER.strip(), ""]
    buttons = []

    for index, playlist in enumerate(playlists, 1):
        name = escape_markdown(playlist.get('name', 'پلی‌لیست'))
        is_private = playlist.get('is_private', False)
        status_icon = '🔒' if is_private else '🌐'
        status_text = 'مخفی' if is_private else 'عمومی'

        message_lines.append(
            MANAGE_VISIBILITY_ITEM.format(
                index=index,
                status_icon=status_icon,
                name=name,
                status=status_text,
            )
        )

        toggle_label = '🔓 عمومی کن' if is_private else '🔒 مخفی کن'
        buttons.append([
            InlineKeyboardButton(
                f"{toggle_label} — {playlist.get('name', 'پلی‌لیست')}",
                callback_data=f"toggle_visibility_{playlist['id']}"
            )
        ])

    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_profile")])

    await send_response(
        update,
        "\n".join(message_lines),
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
        await send_response(update, ERROR_GENERAL, parse_mode=None)
        return

    playlists = db.get_user_playlists(user_id)
    total_songs = sum(len(pl['songs']) for pl in playlists)
    rank = db.get_user_rank(user_id)

    status = "💎 پریمیوم" if db.is_premium(user_id) else "🆓 رایگان"
    badges_text = format_badges(user.get('badges', []))
    added_playlists = db.get_user_added_playlists(user_id)
    added_playlists_count = len(added_playlists)

    profile_text = PROFILE_TEXT.format(
        name=user['first_name'],
        playlists_count=len(playlists),
        songs_count=total_songs,
        added_playlists_count=added_playlists_count,
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
        [InlineKeyboardButton("👁️ مدیریت نمایش", callback_data="manage_visibility")],
        [InlineKeyboardButton(BTN_ADDED_PLAYLISTS, callback_data="added_playlists")],
        [InlineKeyboardButton("📊 آمار کامل", callback_data="my_stats")],
    ]

    if not db.is_premium(user_id):
        buttons.append([InlineKeyboardButton("💎 پریمیوم بگیر", callback_data="premium")])

    await send_response(
        update,
        profile_text,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def show_added_playlists(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display playlists from which the user has saved songs"""
    user_id = update.effective_user.id
    playlists = db.get_user_added_playlists(user_id)

    if not playlists:
        await send_response(
            update,
            NO_ADDED_PLAYLISTS,
            parse_mode=None,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back_profile")]
            ]),
        )
        return

    message_lines = [ADDED_PLAYLISTS_HEADER]
    buttons = []

    for index, playlist in enumerate(playlists, 1):
        owner = db.get_user(int(playlist['owner_id'])) if playlist.get('owner_id') else None

        if owner:
            if owner.get('first_name') and owner['first_name'].lower() != 'unknown':
                owner_name = owner['first_name']
            elif owner.get('username'):
                owner_name = f"@{owner['username']}"
            else:
                owner_name = f"کاربر {owner['user_id'][-4:]}"
        else:
            owner_name = "نامشخص"

        message_lines.append(
            ADDED_PLAYLISTS_ITEM.format(
                index=index,
                name=escape_markdown(playlist['name']),
                owner=escape_markdown(owner_name),
                likes=format_number(len(playlist.get('likes', []))),
                songs=format_number(len(playlist.get('songs', []))),
            )
        )

        buttons.append([
            InlineKeyboardButton(
                f"▶️ {playlist['name']}",
                callback_data=f"play_{playlist['id']}",
            )
        ])

    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_profile")])

    await send_response(
        update,
        "".join(message_lines),
        reply_markup=InlineKeyboardMarkup(buttons),
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

    playlist_limit_display = "بی‌نهایت" if not PREMIUM_PLAYLIST_LIMIT else str(PREMIUM_PLAYLIST_LIMIT)
    songs_limit_display = "بی‌نهایت" if not PREMIUM_SONGS_PER_PLAYLIST else str(PREMIUM_SONGS_PER_PLAYLIST)
    follow_limit_display = (
        "بی‌نهایت" if not PREMIUM_FOLLOW_LIMIT else format_number(PREMIUM_FOLLOW_LIMIT)
    )

    info_text = PREMIUM_INFO.format(
        plans=plan_lines,
        playlist_limit=playlist_limit_display,
        songs_limit=songs_limit_display,
        follow_limit=follow_limit_display,
    )

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
        'uploader_id': str(user_id),
        'uploader_name': update.effective_user.first_name or update.effective_user.full_name,
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
        max_songs_value = updated_playlist.get('max_songs')
        if isinstance(max_songs_value, int):
            if max_songs_value == 0:
                maximum_display = 'بی‌نهایت'
            elif max_songs_value > 0:
                maximum_display = str(max_songs_value)
            else:
                maximum_display = str(max(MIN_SONGS_TO_PUBLISH, updated_count))
        else:
            maximum_display = str(max(MIN_SONGS_TO_PUBLISH, updated_count))

        if remaining > 0:
            auto_hint = f"اگر {remaining} آهنگ دیگه بفرستی خودش خودکار منتشر میشه."
        else:
            auto_hint = "همین حالا می‌تونی منتشرش کنی!"

        await update.message.reply_text(
            PLAYLIST_DRAFT_PROGRESS.format(
                current=updated_count,
                maximum=maximum_display,
                auto_hint=auto_hint,
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

    db.touch_user(user_id)

    # Browse menus
    if data.startswith('help_section:'):
        section = data.split(':', 1)[1]
        await show_help(update, context, section)
        return

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

    elif data.startswith('share_'):
        playlist_id = data.replace('share_', '', 1)
        playlist = db.get_playlist(playlist_id)

        if not playlist:
            await query.answer(ERROR_NOT_FOUND, show_alert=True)
            return

        if playlist.get('status') != 'published' and playlist.get('owner_id') != str(user_id):
            await query.answer(PLAYLIST_NOT_PUBLISHED, show_alert=True)
            return
        if playlist.get('is_private') and playlist.get('owner_id') != str(user_id):
            await query.answer(PLAYLIST_PRIVATE_WARNING, show_alert=True)
            return

        share_url = build_playlist_share_url(playlist_id, playlist.get('name', ''))
        if not share_url:
            await query.answer(ERROR_GENERAL, show_alert=True)
            return

        share_text = SHARE_PLAYLIST_MESSAGE.format(
            name=escape_markdown(playlist.get('name', 'پلی‌لیست')),
            link=share_url,
        )

        await context.bot.send_message(
            chat_id=user_id,
            text=share_text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )

        await query.answer(SHARE_LINK_SENT)

    # Like song (needs to be checked before general like handler)
    elif data.startswith('like_song:'):
        try:
            _, playlist_id, song_id = data.split(':', 2)
        except ValueError:
            await query.answer(ERROR_GENERAL, show_alert=True)
            return

        song = db.data['songs'].get(song_id)
        if not song:
            await query.answer(ERROR_NOT_FOUND, show_alert=True)
            return

        playlist = db.get_playlist(playlist_id)
        is_owner = playlist is not None and playlist.get('owner_id') == str(user_id)

        if str(user_id) in song.get('likes', []):
            db.unlike_song(user_id, song_id)
            await query.answer(UNLIKED)
            liked = False
        else:
            if db.like_song(user_id, song_id):
                await query.answer(LIKED)
                liked = True

                uploader_id = song.get('uploader_id')
                if uploader_id and int(uploader_id) != user_id:
                    liker = db.get_user(user_id)
                    notif_text = NOTIF_SONG_LIKED.format(
                        user=liker['first_name'],
                        song=song.get('title', 'آهنگ'),
                    )
                    await send_notification(int(uploader_id), notif_text, context)

                await send_notification(
                    user_id,
                    NOTIF_SONG_LIKED_SELF.format(song=song.get('title', 'آهنگ')),
                    context,
                )
            else:
                await query.answer(ALREADY_LIKED)
                return

        original_id = song.get('original_song_id', song_id)
        already_added = db.user_has_song_copy(user_id, original_id)
        like_count = len(song.get('likes', []))
        add_count = db.count_song_adds(original_id)
        try:
            await query.message.edit_reply_markup(
                reply_markup=create_song_buttons(
                    song_id,
                    playlist_id,
                    user_liked=liked,
                    already_added=already_added,
                    like_count=like_count,
                    add_count=add_count,
                    can_remove=is_owner,
                )
            )
        except BadRequest as exc:
            logger.warning(
                "BadRequest while updating song buttons after like: %s",
                exc,
            )
        except Exception as exc:
            logger.error(
                "Unexpected error updating song buttons after like: %s",
                exc,
            )

        return

    # Like playlist
    elif data.startswith('like_'):
        playlist_id = data.replace('like_', '')
        playlist = db.get_playlist(playlist_id)

        if not playlist:
            await query.answer(ERROR_NOT_FOUND, show_alert=True)
            return

        if playlist.get('status') != 'published' and playlist.get('owner_id') != str(user_id):
            await query.answer(PLAYLIST_NOT_PUBLISHED, show_alert=True)
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

    elif data.startswith('add_song:'):
        try:
            _, source_playlist_id, song_id = data.split(':', 2)
        except ValueError:
            await query.answer(ERROR_GENERAL, show_alert=True)
            return

        song = db.data['songs'].get(song_id)
        if not song:
            await query.answer(ERROR_NOT_FOUND, show_alert=True)
            return

        user_playlists = db.get_user_playlists(user_id)
        if not user_playlists:
            await query.answer("اول یه پلی‌لیست بساز!", show_alert=True)
            await context.bot.send_message(
                chat_id=user_id,
                text=NEED_PLAYLIST_BEFORE_ADD,
            )
            return

        context.user_data['pending_song_add'] = {
            'song_id': song_id,
            'source_playlist_id': source_playlist_id,
            'message_id': query.message.message_id,
        }

        buttons = [
            [
                InlineKeyboardButton(
                    pl['name'],
                    callback_data=f"add_song_to:{pl['id']}",
                )
            ]
            for pl in user_playlists
        ]

        await context.bot.send_message(
            chat_id=user_id,
            text=CHOOSE_PLAYLIST_TO_SAVE_SONG,
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    elif data.startswith('add_song_to:'):
        target_playlist_id = data.replace('add_song_to:', '')
        pending = context.user_data.get('pending_song_add')
        if not pending:
            await query.answer(ERROR_GENERAL, show_alert=True)
            return

        song_id = pending['song_id']
        original_song = db.data['songs'].get(song_id)
        if not original_song:
            await query.answer(ERROR_NOT_FOUND, show_alert=True)
            return

        success, status = db.add_existing_song_to_playlist(
            song_id,
            target_playlist_id,
            user_id,
        )

        target_playlist = db.get_playlist(target_playlist_id)
        if not target_playlist:
            await query.answer(ERROR_NOT_FOUND, show_alert=True)
            return

        if not success:
            if status == 'duplicate':
                await query.answer(
                    "این آهنگ قبلاً تو این پلی‌لیسته!", show_alert=True
                )
            elif status == 'playlist_full':
                await query.answer(
                    PLAYLIST_FULL.format(max_songs=target_playlist.get('max_songs', 0)),
                    show_alert=True,
                )
            else:
                await query.answer(ERROR_GENERAL, show_alert=True)
            return

        await query.answer("انجام شد! ✅")

        await query.edit_message_text(
            ADDED_TO_PLAYLIST.format(playlist=target_playlist['name'])
        )

        source_uploader = original_song.get('uploader_id')
        if source_uploader and int(source_uploader) != user_id:
            adder = db.get_user(user_id)
            notif_text = NOTIF_ADDED.format(
                user=adder['first_name'],
                song=original_song.get('title', 'آهنگ'),
            )
            await send_notification(int(source_uploader), notif_text, context)

        await send_notification(
            user_id,
            NOTIF_SONG_ADDED_SELF.format(
                song=original_song.get('title', 'آهنگ'),
                playlist=target_playlist['name'],
            ),
            context,
        )

        original_id = original_song.get('original_song_id', song_id)
        like_count = len(original_song.get('likes', []))
        add_count = db.count_song_adds(original_id)
        source_playlist = db.get_playlist(pending['source_playlist_id']) if pending.get('source_playlist_id') else None
        can_remove_source = source_playlist is not None and source_playlist.get('owner_id') == str(user_id)

        try:
            await context.bot.edit_message_reply_markup(
                chat_id=user_id,
                message_id=pending['message_id'],
                reply_markup=create_song_buttons(
                    song_id,
                    pending['source_playlist_id'],
                    user_liked=str(user_id) in original_song.get('likes', []),
                    already_added=True,
                    like_count=like_count,
                    add_count=add_count,
                    can_remove=can_remove_source,
                ),
            )
        except Exception as exc:
            logger.error(f"Failed to update song buttons after add: {exc}")

        context.user_data.pop('pending_song_add', None)

    elif data.startswith('remove_song:'):
        try:
            _, playlist_id, song_id = data.split(':', 2)
        except ValueError:
            await query.answer(ERROR_GENERAL, show_alert=True)
            return

        playlist = db.get_playlist(playlist_id)
        playlist_name = playlist.get('name', 'پلی‌لیست') if playlist else 'پلی‌لیست'

        success, info = db.remove_song_from_playlist(playlist_id, song_id, user_id)

        if not success:
            status = info.get('status') if isinstance(info, dict) else None
            if status == 'not_owner':
                await query.answer(SONG_REMOVE_NOT_OWNER, show_alert=True)
            elif status in {'playlist_not_found', 'song_not_in_playlist'}:
                await query.answer(SONG_REMOVE_NOT_FOUND, show_alert=True)
            else:
                await query.answer(ERROR_GENERAL, show_alert=True)
            return

        storage_messages = info.get('storage_messages', []) if isinstance(info, dict) else []
        for channel_id, message_id in storage_messages:
            try:
                await context.bot.delete_message(chat_id=channel_id, message_id=message_id)
            except BadRequest as exc:
                logger.warning(
                    "BadRequest while deleting song %s from channel %s: %s",
                    song_id,
                    channel_id,
                    exc,
                )
            except Exception as exc:
                logger.error(
                    "Unexpected error deleting song %s from channel %s: %s",
                    song_id,
                    channel_id,
                    exc,
                )

        try:
            await query.message.delete()
        except BadRequest as exc:
            logger.debug("Failed to delete song message after removal: %s", exc)
        except Exception as exc:
            logger.error("Unexpected error deleting song message: %s", exc)

        await query.answer("آهنگ حذف شد!", show_alert=True)

        updated_playlist = db.get_playlist(playlist_id)
        playlist_display_name = playlist_name
        if updated_playlist:
            playlist_display_name = updated_playlist.get('name', playlist_name)

        remaining = info.get('remaining_songs', 0)
        max_songs = info.get('max_songs', 0)
        current_display = format_number(remaining)
        maximum_display = "∞" if not max_songs else format_number(max_songs)

        messages = [
            SONG_REMOVED_SUCCESS.format(playlist=playlist_display_name)
        ]
        messages.append(
            PLAYLIST_CAPACITY_STATUS.format(
                current=current_display,
                maximum=maximum_display,
            )
        )

        if not max_songs or remaining < max_songs:
            messages.append(PLAYLIST_OWNER_ADD_HINT)

        if info.get('playlist_now_draft'):
            messages.append(
                PLAYLIST_OWNER_NOW_DRAFT.format(
                    min_songs=MIN_SONGS_TO_PUBLISH,
                )
            )

        await context.bot.send_message(
            chat_id=user_id,
            text="\n".join(messages),
        )

        return

    # Add to playlist
    elif data.startswith('add_'):
        playlist_id = data.replace('add_', '')
        playlist = db.get_playlist(playlist_id)

        if not playlist:
            await query.answer(ERROR_NOT_FOUND)
            return

        if playlist.get('status') != 'published' and playlist.get('owner_id') != str(user_id):
            await query.answer(PLAYLIST_NOT_PUBLISHED)
            return

        context.user_data['adding_from'] = playlist_id

        # Show user's playlists
        user_playlists = db.get_user_playlists(user_id)
        if not user_playlists:
            await query.answer("اول یه پلی‌لیست بساز!")
            await context.bot.send_message(
                chat_id=user_id,
                text=NEED_PLAYLIST_BEFORE_ADD,
            )
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
            await query.answer(ERROR_NOT_FOUND)
            return

        if playlist.get('status') != 'published' and playlist.get('owner_id') != str(user_id):
            await query.answer(PLAYLIST_NOT_PUBLISHED)
            return
        if playlist.get('is_private') and playlist.get('owner_id') != str(user_id):
            await query.answer(PLAYLIST_PRIVATE_WARNING, show_alert=True)
            return

        if playlist.get('songs'):
            await query.answer(f"در حال پخش {playlist['name']}...")
        else:
            await query.answer("این پلی‌لیست خالیه!")

        await send_playlist_details(user_id, playlist, context, playlist_id)

    elif data.startswith('set_active_add:'):
        playlist_id = data.replace('set_active_add:', '')
        playlist = db.get_playlist(playlist_id)

        if not playlist or playlist.get('owner_id') != str(user_id):
            await query.answer(ERROR_NOT_FOUND, show_alert=True)
            return

        max_songs = playlist.get('max_songs', 0) or 0
        current_count = len(playlist.get('songs', []))
        if max_songs and current_count >= max_songs:
            await query.answer(
                PLAYLIST_FULL.format(max_songs=max_songs),
                show_alert=True,
            )
            return

        user = db.get_user(user_id)
        current_active = user.get('active_playlist_id') if user else None
        if current_active == playlist_id:
            await query.answer(PLAYLIST_ALREADY_ACTIVE, show_alert=True)
            return

        db.set_active_playlist(user_id, playlist_id)
        await query.answer("پلی‌لیست فعال شد!", show_alert=False)

        current_display = format_number(current_count)
        maximum_display = "∞" if not max_songs else format_number(max_songs)
        message_lines = [
            PLAYLIST_ACTIVATED_FOR_UPLOAD.format(name=playlist.get('name', 'پلی‌لیست')),
            PLAYLIST_CAPACITY_STATUS.format(
                current=current_display,
                maximum=maximum_display,
            ),
        ]

        if not max_songs or current_count < max_songs:
            message_lines.append(PLAYLIST_OWNER_ADD_HINT)

        await context.bot.send_message(
            chat_id=user_id,
            text="\n".join(message_lines),
        )

    elif data.startswith('toggle_visibility_'):
        playlist_id = data.replace('toggle_visibility_', '', 1)
        new_state = db.toggle_playlist_visibility(user_id, playlist_id)

        if new_state is None:
            await query.answer(ERROR_GENERAL, show_alert=True)
            return

        if new_state:
            await query.answer(PLAYLIST_NOW_PRIVATE)
        else:
            await query.answer(PLAYLIST_NOW_PUBLIC)

        await manage_playlist_visibility(update, context)

    # User quick actions
    elif data == 'my_playlists':
        await my_playlists(update, context)

    elif data == 'added_playlists':
        await show_added_playlists(update, context)

    elif data == 'premium':
        await premium_info(update, context)

    elif data == 'manage_visibility':
        await manage_playlist_visibility(update, context)

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
        deleted_messages = db.delete_playlist(playlist_id)

        for channel_id, message_id in deleted_messages:
            try:
                await context.bot.delete_message(
                    chat_id=channel_id,
                    message_id=message_id,
                )
            except BadRequest as exc:
                logger.warning(
                    "BadRequest while deleting storage message %s from channel %s: %s",
                    message_id,
                    channel_id,
                    exc,
                )
            except Exception as exc:
                logger.error(
                    "Failed to delete storage message %s from channel %s: %s",
                    message_id,
                    channel_id,
                    exc,
                )

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

    elif data == 'back_profile':
        await profile(update, context)

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

        price_text = format_number(plan['price'])
        buttons = [
            [InlineKeyboardButton("✅ فیلترشکن خاموشه، لینک بساز", callback_data=f"confirm_plan_{plan_id}")],
            [InlineKeyboardButton("🔙 پلن‌های دیگر", callback_data="buy_premium")],
        ]

        await query.edit_message_text(
            PREMIUM_VPN_WARNING.format(
                title=escape_markdown(plan['title']),
                price=price_text,
                days=plan['duration_days'],
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith('confirm_plan_'):
        plan_id = data.replace('confirm_plan_', '')
        plan = db.get_premium_plan(plan_id)

        if not plan:
            await query.answer("پلن پیدا نشد!", show_alert=True)
            return

        payment_data = zarinpal.create_payment(
            amount=plan['price'],
            description=f"خرید {plan['title']} پلی‌لیست - {user_id}",
            user_id=user_id
        )

        if payment_data and payment_data.get('payment_url') and payment_data.get('authority'):
            db.set_pending_payment(
                user_id,
                authority=payment_data['authority'],
                amount=plan['price'],
                plan_id=plan_id,
                title=plan['title'],
                duration_days=plan['duration_days'],
            )

            buttons = [
                [InlineKeyboardButton("💳 پرداخت", url=payment_data['payment_url'])],
                [InlineKeyboardButton("🔙 پلن‌های دیگر", callback_data="buy_premium")],
            ]

            await query.edit_message_text(
                PREMIUM_PAYMENT_INSTRUCTIONS.format(
                    title=escape_markdown(plan['title']),
                    price=plan['price'],
                    days=plan['duration_days'],
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            error_buttons = [[InlineKeyboardButton("🔙 پلن‌های دیگر", callback_data="buy_premium")]]
            await query.edit_message_text(
                "مشکلی در ایجاد لینک پرداخت پیش اومد! لطفاً بعداً تلاش کن.",
                reply_markup=InlineKeyboardMarkup(error_buttons)
            )

    elif data == 'verify_payment':
        user = db.get_user(user_id)
        pending = user.get('pending_payment') if user else None

        if not pending:
            await query.answer(PREMIUM_NO_PENDING_PAYMENT, show_alert=True)
            return

        authority = pending.get('authority')
        amount = pending.get('amount')
        plan_id = pending.get('plan_id')
        duration_days = pending.get('duration_days') or 30

        if not authority or not amount:
            await query.answer(PREMIUM_VERIFY_FAILED, show_alert=True)
            return

        if zarinpal.verify_payment(authority, amount):
            db.activate_premium(
                user_id,
                days=duration_days,
                plan_id=plan_id,
                price=amount,
            )
            db.clear_pending_payment(user_id)

            user = db.get_user(user_id)
            expiry_raw = user.get('premium_until') if user else None
            expiry_date = format_date(expiry_raw) if expiry_raw else "—"

            success_buttons = [[InlineKeyboardButton("🔙 برگشت", callback_data="back_main")]]

            playlist_limit_display = "بی‌نهایت" if not PREMIUM_PLAYLIST_LIMIT else str(PREMIUM_PLAYLIST_LIMIT)
            songs_limit_display = "بی‌نهایت" if not PREMIUM_SONGS_PER_PLAYLIST else str(PREMIUM_SONGS_PER_PLAYLIST)
            follow_limit_display = (
                "بی‌نهایت" if not PREMIUM_FOLLOW_LIMIT else format_number(PREMIUM_FOLLOW_LIMIT)
            )

            await query.edit_message_text(
                PREMIUM_ACTIVATED.format(
                    date=expiry_date,
                    playlist_limit=playlist_limit_display,
                    songs_limit=songs_limit_display,
                    follow_limit=follow_limit_display,
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(success_buttons)
            )

            await context.bot.send_message(
                chat_id=user_id,
                text=PREMIUM_BENEFITS_REMINDER.format(
                    playlist_limit=playlist_limit_display,
                    songs_limit=songs_limit_display,
                    follow_limit=follow_limit_display,
                ),
                parse_mode=ParseMode.MARKDOWN,
            )

            await query.answer("پرداخت با موفقیت تایید شد!", show_alert=True)
        else:
            await query.answer(PREMIUM_VERIFY_FAILED, show_alert=True)


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
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        db.touch_user(user_id)

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
    application.add_handler(CommandHandler("publishplaylist", publish_playlist_command))
    application.add_handler(CommandHandler("finishplaylist", publish_playlist_command))
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
    application.add_handler(CallbackQueryHandler(admin_stats_callback, pattern='^admin_stats$'))

    # Audio handler
    application.add_handler(MessageHandler(filters.AUDIO, handle_audio))

    # Callback handlers
    application.add_handler(CallbackQueryHandler(button_callback))

    # Main menu button handler (MUST be last!)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_main_menu
    ))

    if application.job_queue:
        application.job_queue.run_daily(
            send_daily_top_song,
            time=datetime_time(hour=22, minute=0),
            name='daily_top_song',
        )

    # Start bot
    print("🎵 پلی‌لیست ربات راه‌اندازی شد! 🚀")
    print(f"📍 ربات: {BOT_NAME}")
    print(f"👨‍💼 ادمین‌ها: {ADMIN_IDS}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()