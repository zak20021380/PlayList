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

    if len(user['playlists']) >= limit:
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
        await query.edit_message_text(
            PLAYLIST_CREATED.format(name=playlist_name),
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
        await update.message.reply_text(NO_PLAYLISTS)
        return

    message = "🎵 **پلی‌لیست‌های من:**\n\n"
    buttons = []

    for pl in playlists:
        mood = DEFAULT_MOODS.get(pl['mood'], '🎵')
        songs_count = len(pl['songs'])
        likes_count = len(pl.get('likes', []))

        message += f"{mood} **{pl['name']}**\n"
        message += f"   🎧 {songs_count} آهنگ | ❤️ {likes_count} لایک\n\n"

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

    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons)
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

    await update.message.reply_text(
        BROWSE_MENU,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show trending playlists"""
    playlists = db.get_trending_playlists(limit=20)

    if not playlists:
        await update.message.reply_text("هنوز پلی‌لیست ترندی نیست! اولین نفر باش! 🚀")
        return

    message = TRENDING_HEADER
    buttons = []

    for i, pl in enumerate(playlists[:10], 1):
        rank_emoji = get_rank_emoji(i)
        message += f"{rank_emoji} **{pl['name']}** by {pl['owner_name']}\n"
        message += f"   ▶️ {pl.get('plays', 0)} | ❤️ {len(pl.get('likes', []))}\n\n"

        buttons.append([
            InlineKeyboardButton(
                f"{rank_emoji} {pl['name']}",
                callback_data=f"play_{pl['id']}"
            )
        ])

    await update.message.reply_text(
        message,
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
    top_users = db.get_leaderboard(sort_by='likes', limit=20)
    user_id = update.effective_user.id
    user_rank = db.get_user_rank(user_id)

    message = LEADERBOARD_HEADER.format(period="این هفته")

    for i, user in enumerate(top_users, 1):
        rank_emoji = get_rank_emoji(i)
        premium_badge = "💎" if user['is_premium'] else ""

        message += LEADERBOARD_ITEM.format(
            rank=rank_emoji,
            name=user['name'],
            score=user['score'],
            unit="لایک"
        )
        message += f" {premium_badge}\n"

    if user_rank:
        message += LEADERBOARD_YOUR_RANK.format(rank=user_rank)

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
    info_text = PREMIUM_INFO.format(price=format_number(PREMIUM_PRICE))

    buttons = [
        [InlineKeyboardButton("💳 خرید پریمیوم", callback_data="buy_premium")],
    ]

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

    # Check caption
    caption = update.message.caption
    if not caption:
        await update.message.reply_text(ERROR_NO_CAPTION)
        return

    # Find playlist
    user_playlists = db.get_user_playlists(user_id)
    playlist = None

    for pl in user_playlists:
        if pl['name'].lower() == caption.lower():
            playlist = pl
            break

    if not playlist:
        playlists_list = "\n".join([f"• {pl['name']}" for pl in user_playlists])
        await update.message.reply_text(
            UPLOAD_NO_PLAYLIST.format(playlists=playlists_list if playlists_list else "هنوز پلی‌لیستی نساختی!")
        )
        return

    # Check upload limit
    user = db.get_user(user_id)
    is_premium = db.is_premium(user_id)
    limit = PREMIUM_UPLOAD_LIMIT if is_premium else FREE_UPLOAD_LIMIT

    if user['total_songs_uploaded'] >= limit:
        await update.message.reply_text(
            UPLOAD_LIMIT_REACHED.format(limit=limit),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Get audio info
    audio = update.message.audio
    song_data = {
        'file_id': audio.file_id,
        'title': audio.title or 'Unknown',
        'performer': audio.performer or 'Unknown',
        'duration': audio.duration or 0,
        'file_size': audio.file_size or 0,
    }

    # Add to playlist
    if db.add_song_to_playlist(playlist['id'], song_data):
        await update.message.reply_text(
            UPLOAD_SUCCESS.format(playlist=playlist['name']),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(ERROR_GENERAL)


# ===== CALLBACK HANDLERS =====




async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = update.effective_user.id

    # Like playlist
    if data.startswith('like_'):
        playlist_id = data.replace('like_', '')
        playlist = db.get_playlist(playlist_id)

        if not playlist:
            await query.edit_message_text(ERROR_NOT_FOUND)
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

        if not playlist or not playlist['songs']:
            await query.answer("این پلی‌لیست خالیه!")
            return

        # Increment plays
        db.increment_plays(playlist_id)

        # Send all songs
        await query.answer(f"در حال پخش {playlist['name']}...")

        for song_id in playlist['songs']:
            song = db.data['songs'].get(song_id)
            if song:
                caption = get_song_info(song)
                try:
                    await context.bot.send_audio(
                        chat_id=user_id,
                        audio=song['file_id'],
                        caption=caption,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=create_song_buttons(song_id, playlist_id)
                    )
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Failed to send audio: {e}")

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
        # Create ZarinPal payment
        payment_url = zarinpal.create_payment(
            amount=PREMIUM_PRICE,
            description=f"خرید پریمیوم پلی‌لیست - {user_id}",
            user_id=user_id
        )

        if payment_url:
            buttons = [
                [InlineKeyboardButton("💳 پرداخت", url=payment_url)],
            ]
            await query.edit_message_text(
                PREMIUM_PAYMENT_INSTRUCTIONS.format(price=format_number(PREMIUM_PRICE)),
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