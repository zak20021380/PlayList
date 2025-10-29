# admin.py - Advanced Admin Panel
# پنل پیشرفته ادمین

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
import asyncio

from config import *
from database import db
from utils import *
from texts import *

# Conversation states for admin
BROADCAST_MESSAGE, BAN_USER_ID, GIVE_PREMIUM_ID, GIVE_PREMIUM_DAYS, SET_PRICE = range(5)


# ===== ADMIN STATS =====

async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed admin statistics"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    stats = db.get_global_stats()
    stats_text = format_admin_stats(stats)

    buttons = [
        [InlineKeyboardButton("🔄 بروزرسانی", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="admin_panel")],
    ]

    await query.edit_message_text(
        stats_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ===== USER MANAGEMENT =====

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User management menu"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    total_users = len(db.data['users'])
    banned_users = len([u for u in db.data['users'].values() if u.get('banned')])
    premium_users = len([u for u in db.data['users'].values() if u.get('premium')])

    message = f"""
👥 **مدیریت کاربران**

📊 کل کاربرها: {total_users}
💎 پریمیوم: {premium_users}
⛔️ بن شده: {banned_users}

از دکمه‌های زیر استفاده کن:
"""

    buttons = [
        [InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="admin_search_user")],
        [InlineKeyboardButton("⛔️ بن کاربر", callback_data="admin_ban_user")],
        [InlineKeyboardButton("✅ آنبن کاربر", callback_data="admin_unban_user")],
        [InlineKeyboardButton("🗑️ حذف کاربر", callback_data="admin_delete_user")],
        [InlineKeyboardButton("📋 لیست بن شده‌ها", callback_data="admin_banned_list")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="admin_panel")],
    ]

    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def admin_ban_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start banning user"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    await query.edit_message_text("آیدی عددی کاربر رو بفرست:")
    return BAN_USER_ID


async def admin_ban_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive user ID to ban"""
    try:
        user_id = int(update.message.text)

        if user_id in ADMIN_IDS:
            await update.message.reply_text("نمیتونی ادمین رو بن کنی! 😅")
            return ConversationHandler.END

        user = db.get_user(user_id)
        if not user:
            await update.message.reply_text("کاربر پیدا نشد!")
            return ConversationHandler.END

        # Ban user
        db.ban_user(user_id)

        await update.message.reply_text(
            f"✅ کاربر بن شد!\n\n👤 {user['first_name']}\n🆔 {user_id}"
        )

    except ValueError:
        await update.message.reply_text("آیدی عددی وارد کن!")
        return BAN_USER_ID

    return ConversationHandler.END


async def admin_unban_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start unbanning user"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    # Show list of banned users
    banned = [u for u in db.data['users'].values() if u.get('banned')]

    if not banned:
        await query.edit_message_text("هیچ کاربر بن شده‌ای وجود نداره!")
        return

    message = "⛔️ **کاربران بن شده:**\n\n"
    buttons = []

    for user in banned[:20]:  # Show first 20
        message += f"👤 {user['first_name']} - `{user['user_id']}`\n"
        buttons.append([
            InlineKeyboardButton(
                f"✅ آنبن {user['first_name']}",
                callback_data=f"unban_{user['user_id']}"
            )
        ])

    buttons.append([InlineKeyboardButton("🔙 برگشت", callback_data="admin_users")])

    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def admin_unban_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban user callback"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    user_id = int(query.data.replace('unban_', ''))
    db.unban_user(user_id)

    await query.answer("✅ کاربر آنبن شد!")
    await admin_unban_user_start(update, context)


# ===== PREMIUM MANAGEMENT =====

async def admin_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Premium management menu"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    premium_users = [u for u in db.data['users'].values() if u.get('premium')]
    total_revenue = len(premium_users) * PREMIUM_PRICE

    message = f"""
💎 **مدیریت پریمیوم**

📊 کاربران پریمیوم: {len(premium_users)}
💰 درآمد کل: {format_number(total_revenue)} تومان
💳 قیمت فعلی: {format_number(PREMIUM_PRICE)} تومان

از دکمه‌های زیر استفاده کن:
"""

    buttons = [
        [InlineKeyboardButton("💎 دادن پریمیوم", callback_data="admin_give_premium")],
        [InlineKeyboardButton("📋 لیست پریمیوم‌ها", callback_data="admin_premium_list")],
        [InlineKeyboardButton("💰 تغییر قیمت", callback_data="admin_set_price")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="admin_panel")],
    ]

    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def admin_give_premium_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start giving premium"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    await query.edit_message_text("آیدی کاربر رو بفرست:")
    return GIVE_PREMIUM_ID


async def admin_give_premium_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive user ID for premium"""
    try:
        user_id = int(update.message.text)
        user = db.get_user(user_id)

        if not user:
            await update.message.reply_text("کاربر پیدا نشد!")
            return ConversationHandler.END

        context.user_data['premium_user_id'] = user_id
        await update.message.reply_text(
            f"برای چند روز؟\n(پیشفرض: {PREMIUM_DURATION_DAYS} روز)"
        )
        return GIVE_PREMIUM_DAYS

    except ValueError:
        await update.message.reply_text("آیدی عددی وارد کن!")
        return GIVE_PREMIUM_ID


async def admin_give_premium_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive duration for premium"""
    try:
        days = int(update.message.text)
        user_id = context.user_data['premium_user_id']

        # Activate premium
        db.activate_premium(user_id, days)

        user = db.get_user(user_id)
        await update.message.reply_text(
            f"✅ پریمیوم فعال شد!\n\n"
            f"👤 {user['first_name']}\n"
            f"⏰ مدت: {days} روز"
        )

        # Notify user
        try:
            expiry_date = format_date(user['premium_until'])
            await context.bot.send_message(
                chat_id=user_id,
                text=PREMIUM_ACTIVATED.format(date=expiry_date),
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass

    except ValueError:
        await update.message.reply_text("عدد وارد کن!")
        return GIVE_PREMIUM_DAYS

    return ConversationHandler.END


async def admin_premium_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of premium users"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    premium_users = [u for u in db.data['users'].values() if u.get('premium')]

    if not premium_users:
        await query.edit_message_text("هیچ کاربر پریمیومی نیست!")
        return

    message = "💎 **کاربران پریمیوم:**\n\n"

    for user in premium_users[:30]:  # Show first 30
        expiry = format_date(user.get('premium_until', ''))
        message += f"👤 {user['first_name']}\n"
        message += f"   🆔 `{user['user_id']}` | ⏰ تا {expiry}\n\n"

    buttons = [[InlineKeyboardButton("🔙 برگشت", callback_data="admin_premium")]]

    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def admin_set_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start changing premium price"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    await query.edit_message_text(
        f"قیمت فعلی: {format_number(PREMIUM_PRICE)} تومان\n\n"
        f"قیمت جدید رو بفرست:"
    )
    return SET_PRICE


async def admin_set_price_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive new premium price"""
    try:
        new_price = int(update.message.text)

        if new_price < 1000:
            await update.message.reply_text("قیمت باید حداقل 1000 تومان باشه!")
            return SET_PRICE

        # Update price in config (need to modify config dynamically or save to db)
        # For now, just inform admin to update config.py manually
        await update.message.reply_text(
            f"✅ برای تغییر قیمت به {format_number(new_price)} تومان:\n\n"
            f"1. فایل config.py رو باز کن\n"
            f"2. PREMIUM_PRICE رو به {new_price} تغییر بده\n"
            f"3. ربات رو ریستارت کن"
        )

    except ValueError:
        await update.message.reply_text("عدد وارد کن!")
        return SET_PRICE

    return ConversationHandler.END


# ===== BROADCAST =====

async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start broadcast"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton("📢 همه کاربرها", callback_data="broadcast_all")],
        [InlineKeyboardButton("💎 فقط پریمیوم‌ها", callback_data="broadcast_premium")],
        [InlineKeyboardButton("🆓 فقط رایگان‌ها", callback_data="broadcast_free")],
        [InlineKeyboardButton("❌ لغو", callback_data="admin_panel")],
    ]

    await query.edit_message_text(
        "📢 **ارسال پیام همگانی**\n\nبه کی میخوای ارسال کنی؟",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def admin_broadcast_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Select broadcast type"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    broadcast_type = query.data.replace('broadcast_', '')
    context.user_data['broadcast_type'] = broadcast_type

    await query.edit_message_text("پیامت رو بفرست:")
    return BROADCAST_MESSAGE


async def admin_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send broadcast message"""
    message_text = update.message.text
    broadcast_type = context.user_data.get('broadcast_type', 'all')

    # Get target users
    if broadcast_type == 'all':
        target_users = [u for u in db.data['users'].values() if not u.get('banned')]
    elif broadcast_type == 'premium':
        target_users = [u for u in db.data['users'].values() if u.get('premium') and not u.get('banned')]
    else:  # free
        target_users = [u for u in db.data['users'].values() if not u.get('premium') and not u.get('banned')]

    await update.message.reply_text(
        f"در حال ارسال به {len(target_users)} کاربر...\n"
        f"این ممکنه چند دقیقه طول بکشه ⏳"
    )

    # Send to all
    success = 0
    failed = 0

    for user in target_users:
        try:
            await context.bot.send_message(
                chat_id=int(user['user_id']),
                text=f"📢 **پیام از ادمین:**\n\n{message_text}",
                parse_mode=ParseMode.MARKDOWN
            )
            success += 1
            await asyncio.sleep(0.1)  # Avoid rate limits
        except Exception as e:
            failed += 1
            logger.error(f"Failed to send broadcast to {user['user_id']}: {e}")

    await update.message.reply_text(
        f"✅ ارسال تموم شد!\n\n"
        f"موفق: {success}\n"
        f"ناموفق: {failed}"
    )

    return ConversationHandler.END


# ===== CONTENT MODERATION =====

async def admin_delete_playlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete any playlist (admin)"""
    # Admin can use: /deleteplaylist <playlist_id>
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("استفاده: /deleteplaylist <playlist_id>")
        return

    playlist_id = context.args[0]
    playlist = db.get_playlist(playlist_id)

    if not playlist:
        await update.message.reply_text("پلی‌لیست پیدا نشد!")
        return

    db.delete_playlist(playlist_id)
    await update.message.reply_text(
        f"✅ پلی‌لیست حذف شد!\n\n"
        f"📁 {playlist['name']}\n"
        f"👤 صاحب: {playlist['owner_name']}"
    )


async def admin_feature_playlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Feature a playlist (admin)"""
    # Admin can use: /feature <playlist_id>
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("استفاده: /feature <playlist_id>")
        return

    playlist_id = context.args[0]
    playlist = db.get_playlist(playlist_id)

    if not playlist:
        await update.message.reply_text("پلی‌لیست پیدا نشد!")
        return

    # Mark as featured (you can add a 'featured' field to database)
    playlist['featured'] = True
    db.save_data()

    await update.message.reply_text(
        f"✅ پلی‌لیست فیچر شد!\n\n"
        f"📁 {playlist['name']}\n"
        f"👤 {playlist['owner_name']}"
    )


# ===== ADMIN PANEL CALLBACK =====

async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin panel"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    buttons = [
        [InlineKeyboardButton("📊 آمار", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_users")],
        [InlineKeyboardButton("💎 مدیریت پریمیوم", callback_data="admin_premium")],
        [InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast")],
    ]

    await query.edit_message_text(
        ADMIN_PANEL,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# Export functions for use in main bot
__all__ = [
    'admin_stats_callback',
    'admin_users',
    'admin_ban_user_start',
    'admin_ban_user_id',
    'admin_unban_user_start',
    'admin_unban_callback',
    'admin_premium',
    'admin_give_premium_start',
    'admin_give_premium_id',
    'admin_give_premium_days',
    'admin_premium_list',
    'admin_set_price_start',
    'admin_set_price_value',
    'admin_broadcast_start',
    'admin_broadcast_type',
    'admin_broadcast_send',
    'admin_delete_playlist',
    'admin_feature_playlist',
    'admin_panel_callback',
]