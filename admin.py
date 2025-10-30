# admin.py - Advanced Admin Panel
# پنل پیشرفته ادمین

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
import asyncio
import logging

from config import *
from database import db
from utils import *
from texts import *


logger = logging.getLogger(__name__)

# Conversation states for admin
(
    BROADCAST_MESSAGE,
    BAN_USER_ID,
    GIVE_PREMIUM_ID,
    GIVE_PREMIUM_DAYS,
    ADD_PLAN_TITLE,
    ADD_PLAN_PRICE,
    ADD_PLAN_DURATION,
    EDIT_PLAN_PRICE,
    EDIT_PLAN_DURATION,
) = range(9)


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

def build_admin_premium_overview():
    """Create premium overview text and keyboard"""
    premium_users = [u for u in db.data['users'].values() if u.get('premium')]
    revenue = sum(u.get('premium_price', 0) or 0 for u in premium_users)
    plans = db.get_premium_plans()

    if plans:
        plan_lines = "\n".join(
            [
                f"• {escape_markdown(plan['title'])} — {format_number(plan['price'])} تومان / {plan['duration_days']} روز"
                for plan in plans
            ]
        )
    else:
        plan_lines = "پلنی ثبت نشده!"

    message = f"""
💎 **مدیریت پریمیوم**

📊 کاربران پریمیوم: {len(premium_users)}
💰 درآمد کل: {format_number(revenue)} تومان

**پلن‌های فعال:**
{plan_lines}

از دکمه‌های زیر استفاده کن:
"""

    buttons = [
        [InlineKeyboardButton("💎 دادن پریمیوم", callback_data="admin_give_premium")],
        [InlineKeyboardButton("📋 لیست پریمیوم‌ها", callback_data="admin_premium_list")],
    ]

    for plan in plans:
        buttons.append([
            InlineKeyboardButton(
                f"✏️ مدیریت {plan['title']}",
                callback_data=f"admin_edit_plan_{plan['id']}"
            )
        ])

    buttons.append([InlineKeyboardButton("➕ افزودن پلن جدید", callback_data="admin_add_plan")])
    buttons.append([InlineKeyboardButton("🔙 برگشت", callback_data="admin_panel")])

    return message, InlineKeyboardMarkup(buttons)


async def admin_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Premium management menu"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    message, markup = build_admin_premium_overview()

    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup
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

        default_plan = db.get_premium_plans()[0] if db.get_premium_plans() else None
        default_days = default_plan['duration_days'] if default_plan else 30

        context.user_data['premium_user_id'] = user_id
        await update.message.reply_text(
            f"برای چند روز؟\n(پیشفرض: {default_days} روز)"
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
        db.activate_premium(user_id, days=days, plan_id='manual', price=0)

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


async def admin_add_plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for new plan title"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    await query.edit_message_text("اسم پلن جدید رو بفرست:")
    return ADD_PLAN_TITLE


async def admin_add_plan_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive plan title"""
    title = update.message.text.strip()

    if len(title) < 2:
        await update.message.reply_text("اسم پلن خیلی کوتاهه! دوباره بفرست:")
        return ADD_PLAN_TITLE

    context.user_data['new_plan_title'] = title
    await update.message.reply_text("قیمت پلن (تومان) رو بفرست:")
    return ADD_PLAN_PRICE


async def admin_add_plan_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive plan price"""
    try:
        price = int(update.message.text.replace(',', '').strip())
    except ValueError:
        await update.message.reply_text("قیمت باید عدد باشه! دوباره بفرست:")
        return ADD_PLAN_PRICE

    if price < 1000:
        await update.message.reply_text("قیمت باید حداقل 1000 تومان باشه!")
        return ADD_PLAN_PRICE

    context.user_data['new_plan_price'] = price
    await update.message.reply_text("مدت پلن چند روزه باشه؟")
    return ADD_PLAN_DURATION


async def admin_add_plan_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive plan duration and save"""
    try:
        days = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("مدت باید عدد باشه! دوباره بفرست:")
        return ADD_PLAN_DURATION

    if days <= 0:
        await update.message.reply_text("مدت باید بزرگتر از صفر باشه!")
        return ADD_PLAN_DURATION

    title = context.user_data.pop('new_plan_title', 'پلن جدید')
    price = context.user_data.pop('new_plan_price', 0)
    plan = db.add_premium_plan(title=title, price=price, duration_days=days)

    await update.message.reply_text(ADMIN_PLAN_CREATED.format(title=plan['title']))

    overview_text, markup = build_admin_premium_overview()
    await update.message.reply_text(
        overview_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup
    )

    return ConversationHandler.END


async def admin_edit_plan_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show specific plan management menu"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    plan_id = query.data.replace('admin_edit_plan_', '')
    plan = db.get_premium_plan(plan_id)

    if not plan:
        await query.edit_message_text("پلن پیدا نشد!")
        return

    message = (
        f"💎 **{escape_markdown(plan['title'])}**\n\n"
        f"💰 قیمت: {format_number(plan['price'])} تومان\n"
        f"⏱ مدت: {plan['duration_days']} روز"
    )

    buttons = [
        [InlineKeyboardButton("💰 تغییر قیمت", callback_data=f"admin_plan_price_{plan_id}")],
        [InlineKeyboardButton("⏱ تغییر مدت", callback_data=f"admin_plan_duration_{plan_id}")],
    ]

    if len(db.get_premium_plans()) > 1:
        buttons.append([
            InlineKeyboardButton("🗑 حذف پلن", callback_data=f"admin_plan_delete_{plan_id}")
        ])

    buttons.append([InlineKeyboardButton("🔙 برگشت", callback_data="admin_premium")])

    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def admin_plan_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt for new price"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    plan_id = query.data.replace('admin_plan_price_', '')
    plan = db.get_premium_plan(plan_id)

    if not plan:
        await query.edit_message_text("پلن پیدا نشد!")
        return ConversationHandler.END

    context.user_data['edit_plan_id'] = plan_id

    await query.edit_message_text(
        f"قیمت فعلی {plan['title']}: {format_number(plan['price'])} تومان\n\n"
        "قیمت جدید رو بفرست:"
    )
    return EDIT_PLAN_PRICE


async def admin_plan_price_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save new plan price"""
    plan_id = context.user_data.get('edit_plan_id')

    if not plan_id:
        await update.message.reply_text("پلن مشخص نیست! دوباره تلاش کن.")
        return ConversationHandler.END

    try:
        price = int(update.message.text.replace(',', '').strip())
    except ValueError:
        await update.message.reply_text("قیمت باید عدد باشه! دوباره بفرست:")
        return EDIT_PLAN_PRICE

    if price < 1000:
        await update.message.reply_text("قیمت باید حداقل 1000 تومان باشه!")
        return EDIT_PLAN_PRICE

    db.update_premium_plan(plan_id, price=price)
    plan = db.get_premium_plan(plan_id)

    await update.message.reply_text(ADMIN_PLAN_UPDATED.format(title=plan['title']))

    overview_text, markup = build_admin_premium_overview()
    await update.message.reply_text(
        overview_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup
    )

    context.user_data.pop('edit_plan_id', None)
    return ConversationHandler.END


async def admin_plan_duration_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt for new duration"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    plan_id = query.data.replace('admin_plan_duration_', '')
    plan = db.get_premium_plan(plan_id)

    if not plan:
        await query.edit_message_text("پلن پیدا نشد!")
        return ConversationHandler.END

    context.user_data['edit_plan_id'] = plan_id

    await query.edit_message_text(
        f"مدت فعلی {plan['title']}: {plan['duration_days']} روز\n\n"
        "مدت جدید (به روز) رو بفرست:"
    )
    return EDIT_PLAN_DURATION


async def admin_plan_duration_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save new plan duration"""
    plan_id = context.user_data.get('edit_plan_id')

    if not plan_id:
        await update.message.reply_text("پلن مشخص نیست! دوباره تلاش کن.")
        return ConversationHandler.END

    try:
        days = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("مدت باید عدد باشه! دوباره بفرست:")
        return EDIT_PLAN_DURATION

    if days <= 0:
        await update.message.reply_text("مدت باید بزرگتر از صفر باشه!")
        return EDIT_PLAN_DURATION

    db.update_premium_plan(plan_id, duration_days=days)
    plan = db.get_premium_plan(plan_id)

    await update.message.reply_text(ADMIN_PLAN_UPDATED.format(title=plan['title']))

    overview_text, markup = build_admin_premium_overview()
    await update.message.reply_text(
        overview_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup
    )

    context.user_data.pop('edit_plan_id', None)
    return ConversationHandler.END


async def admin_plan_delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for delete confirmation"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    plan_id = query.data.replace('admin_plan_delete_', '')
    plan = db.get_premium_plan(plan_id)

    if not plan:
        await query.edit_message_text("پلن پیدا نشد!")
        return

    buttons = [
        [InlineKeyboardButton("✅ بله حذف کن", callback_data=f"admin_plan_delete_confirm_{plan_id}")],
        [InlineKeyboardButton("❌ انصراف", callback_data=f"admin_edit_plan_{plan_id}")],
    ]

    await query.edit_message_text(
        f"آیا از حذف پلن {plan['title']} مطمئنی؟",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def admin_plan_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete plan after confirmation"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    plan_id = query.data.replace('admin_plan_delete_confirm_', '')
    plan = db.get_premium_plan(plan_id)

    if not plan:
        await query.edit_message_text("پلن پیدا نشد!")
        return

    db.delete_premium_plan(plan_id)

    await query.answer(ADMIN_PLAN_DELETED.format(title=plan['title']))

    message, markup = build_admin_premium_overview()
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup
    )


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
    'admin_add_plan_start',
    'admin_add_plan_title',
    'admin_add_plan_price',
    'admin_add_plan_duration',
    'admin_edit_plan_menu',
    'admin_plan_price_start',
    'admin_plan_price_value',
    'admin_plan_duration_start',
    'admin_plan_duration_value',
    'admin_plan_delete_start',
    'admin_plan_delete_confirm',
    'admin_broadcast_start',
    'admin_broadcast_type',
    'admin_broadcast_send',
    'admin_delete_playlist',
    'admin_feature_playlist',
    'admin_panel_callback',
]