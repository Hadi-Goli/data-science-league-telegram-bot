import os
import io
import logging
import pandas as pd

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from database import db
from utils import check_whitelist, calculate_score

# States for ConversationHandler
AUTH_NAME = 1

# Messages (Persian)
MSG_START = "سلام! به ربات لیگ علم داده خوش آمدید. \nلطفا برای احراز هویت، نام و نام خانوادگی خود را دقیقا همانطور که ثبت نام کرده‌اید وارد کنید."
MSG_ALREADY_REGISTERED = "شما قبلا ثبت نام شده‌اید. می‌توانید فایل CSV خود را ارسال کنید."
MSG_AUTH_SUCCESS = "احراز هویت با موفقیت انجام شد! ✅\nاکنون می‌توانید فایل submissions.csv خود را ارسال کنید تا ارزیابی شود."
MSG_AUTH_FAIL = "متاسفانه نام شما در لیست مجاز یافت نشد یا قبلا ثبت شده است. لطفا با ادمین تماس بگیرید یا نام را دقیق‌تر وارد کنید."
MSG_UPLOAD_INSTRUCTION = "لطفا فایل CSV خود را آپلود کنید. (توجه: فایل باید فرمت صحیح داشته باشد)"
MSG_PROCESSING = "در حال بررسی فایل... ⏳"
MSG_ONLY_CSV = "لطفا فقط فایل CSV ارسال کنید."
MSG_ADMIN_ONLY = "شما دسترسی ادمین ندارید."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await db.get_user(user.id)
    
    if db_user:
        await update.message.reply_text(MSG_ALREADY_REGISTERED)
        await update.message.reply_text(MSG_UPLOAD_INSTRUCTION)
        return ConversationHandler.END
    
    await update.message.reply_text(MSG_START)
    return AUTH_NAME

async def auth_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_name_input = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Check Whitelist
    if check_whitelist(full_name_input):
        # Check if name is already taken (unique constraint handles this, but nice to check)
        # We'll just rely on DB constraint or simple check if we had a method.
        # Ideally check if this full_name is already bound.
        
        try:
            # Check for Admin match logic if needed, usually we set admin in DB directly or by ENV first time.
            # But let's stick to requirement: "If matched ... bind telegram_id"
            
            # Simple Hack: If FIRST_ADMIN_ID matches, make them admin
            is_admin = False
            first_admin = os.getenv("FIRST_ADMIN_ID")
            if first_admin and str(user_id) == str(first_admin):
                is_admin = True
                
            await db.create_user(telegram_id=user_id, full_name=full_name_input, is_admin=is_admin)
            await update.message.reply_text(MSG_AUTH_SUCCESS)
            return ConversationHandler.END
            
        except Exception as e:
            # Likely IntegrityError if full_name already exists for another ID
            await update.message.reply_text(f"خطا: ممکن است این نام قبلا ثبت شده باشد. \n{str(e)}")
            return AUTH_NAME # Ask again?
            
    else:
        await update.message.reply_text(MSG_AUTH_FAIL)
        return AUTH_NAME

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db_user = await db.get_user(user_id)
    
    if not db_user:
        await update.message.reply_text("شما هنوز ثبت نام نکرده‌اید. لطفا /start را بزنید.")
        return

    document = update.message.document
    file_name = document.file_name
    
    if not file_name.lower().endswith('.csv'):
        await update.message.reply_text(MSG_ONLY_CSV)
        return

    # Check competition freeze (if implemented). For now skip.

    status_msg = await update.message.reply_text(MSG_PROCESSING)
    
    try:
        # Download file
        file_obj = await document.get_file()
        file_bytes = await file_obj.download_as_bytearray()
        
        # Calculate RMSE
        # We need the solution file path. 
        # Requirement says: "store this in the repo root"
        solution_path = os.path.join(os.getcwd(), 'solution.csv')
        
        score, error = calculate_score(file_bytes, solution_path)
        
        if error:
            await status_msg.edit_text(f"❌ خطا در ارزیابی:\n{error}")
            return
            
        # Success, save to DB
        new_best = await db.add_submission(user_id, score, file_name)
        rank = await db.get_user_rank(user_id)
        
        response = (
            f"✅ فایل دریافت شد!\n\n"
            f"📉 خطای RMSE شما: {score:.5f}\n"
            f"🏆 بهترین رکورد شما: {new_best:.5f}\n"
            f"📊 رتبه فعلی شما: {rank}"
        )
        await status_msg.edit_text(response)
        
    except Exception as e:
        await status_msg.edit_text(f"خطای سیستمی: {str(e)}")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_users = await db.get_leaderboard(limit=10)
    if not top_users:
        await update.message.reply_text("هنوز رکوردی ثبت نشده است.")
        return
        
    text = "🏆 **جدول امتیازات** 🏆\n\n"
    for i, u in enumerate(top_users, 1):
        # Medal for top 3
        medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
        text += f"{medal} {u.full_name}: {u.best_rmse:.5f}\n"
        
    await update.message.reply_text(text, parse_mode='Markdown')

async def my_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rank = await db.get_user_rank(user_id)
    if not rank:
         await update.message.reply_text("شما هنوز رتبه‌ای ندارید.")
    else:
         await update.message.reply_text(f"📊 رتبه فعلی شما: {rank}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 **راهنمای ربات لیگ علم داده:**\n\n"
        "لیست دستورات قابل استفاده:\n\n"
        "/start - شروع ثبت نام و احراز هویت 📝\n"
        "/help - نمایش همین راهنما ℹ️\n"
        "/leaderboard - مشاهده ۱۰ نفر برتر 🏆\n"
        "/rank - مشاهده رتبه و رکورد شخصی 📊\n\n"
        "📤 **نحوه ارسال پاسخ:**\n"
        "فایل CSV خود را (با نام دلخواه) در چت آپلود کنید. ربات به صورت خودکار آن را بررسی و نمره دهی می‌کند.\n\n"
        "👨‍💻 **ادمین:**\n"
        "/admin - ورود به پنل مدیریت (مخصوص ادمین‌ها)"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

# Admin Conversational States
ADMIN_BROADCAST_MSG = 2
ADMIN_ADD_USER = 3
ADMIN_REMOVE_USER = 4

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    if not user or not user.is_admin:
        await update.message.reply_text(MSG_ADMIN_ONLY)
        return

    # Check freeze status
    is_frozen = await db.get_config("competition_frozen") == "true"
    freeze_text = "باز کردن مسابقه" if is_frozen else "بستن مسابقه"
    freeze_data = "admin_unfreeze" if is_frozen else "admin_freeze"

    keyboard = [
        [InlineKeyboardButton("اضافه کردن کاربر", callback_data='admin_add_user'),
         InlineKeyboardButton("حذف کاربر", callback_data='admin_remove_user')],
        [InlineKeyboardButton("خروجی اکسل (CSV)", callback_data='admin_export')],
        [InlineKeyboardButton(freeze_text, callback_data=freeze_data)],
        [InlineKeyboardButton("ارسال پیام همگانی", callback_data='admin_broadcast')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # If called via callback (back button) or command
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("پنل مدیریت:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("پنل مدیریت:", reply_markup=reply_markup)

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == 'admin_export':
        status_msg = await query.message.reply_text("در حال تولید فایل... ⏳")
        try:
            # We can use pandas to dump tables
            # Ideally fetch all data from DB
            users = await db.get_all_users()
            if not users:
                await status_msg.edit_text("هیچ کاربری یافت نشد.")
                return

            # Flatten data for CSV
            data_list = []
            for u in users:
                data_list.append({
                     "Telegram ID": u.telegram_id,
                     "Full Name": u.full_name,
                     "Best RMSE": u.best_rmse if u.best_rmse != float('inf') else None,
                     "Submission Count": u.submission_count,
                     "Joined At": u.joined_at
                })
            
            df = pd.DataFrame(data_list)
            
            # Create bytes buffer
            output = io.BytesIO()
            df.to_csv(output, index=False)
            output.seek(0)
            
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=output,
                filename="users_export.csv",
                caption="لیست کاربران و وضعیت فعلی"
            )
            await status_msg.delete()
            
        except Exception as e:
            await status_msg.edit_text(f"خطا در ایجاد خروجی: {e}")

    elif data in ['admin_freeze', 'admin_unfreeze']:
        new_value = "true" if data == 'admin_freeze' else "false"
        await db.set_config("competition_frozen", new_value)
        action_text = "مسابقه بسته شد. ⛔️" if new_value == "true" else "مسابقه باز شد. ✅"
        await query.message.reply_text(action_text)
        # Refresh panel
        await admin_panel(update, context)

    elif data == 'admin_broadcast':
        await query.message.reply_text("لطفا متن پیام همگانی را وارد کنید (یا /cancel را بزنید):")
        return ADMIN_BROADCAST_MSG
        
    elif data == 'admin_add_user':
        await query.message.reply_text("نام کامل کاربر را برای اضافه شدن به لیست مجاز وارد کنید:")
        return ADMIN_ADD_USER

    elif data == 'admin_remove_user':
        await query.message.reply_text("نام کامل کاربر را برای حذف از لیست مجاز وارد کنید:")
        return ADMIN_REMOVE_USER

# --- Admin Conversation Handlers ---

async def admin_broadcast_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    users = await db.get_all_users()
    count = 0
    
    status = await update.message.reply_text(f"در حال ارسال به {len(users)} کاربر...")
    
    for u in users:
        try:
            await context.bot.send_message(chat_id=u.telegram_id, text=f"📢 **پیام مدیریت:**\n\n{text}", parse_mode='Markdown')
            count += 1
        except Exception as e:
            logging.error(f"Failed to send to {u.telegram_id}: {e}")
    
    await status.edit_text(f"پیام شما با موفقیت به {count} کاربر ارسال شد.")
    return ConversationHandler.END

async def admin_add_user_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    await db.add_allowed_user(name)
    await update.message.reply_text(f"کاربر '{name}' به لیست مجاز اضافه شد.")
    return ConversationHandler.END

async def admin_remove_user_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    await db.remove_allowed_user(name)
    await update.message.reply_text(f"کاربر '{name}' از لیست مجاز حذف شد.")
    return ConversationHandler.END

async def auth_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_name_input = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Check Whitelist (Now Async)
    if await check_whitelist(full_name_input):
        # ... existing logic ...
        try:
            is_admin = False
            first_admin = os.getenv("FIRST_ADMIN_ID")
            if first_admin and str(user_id) == str(first_admin):
                is_admin = True
                
            await db.create_user(telegram_id=user_id, full_name=full_name_input, is_admin=is_admin)
            await update.message.reply_text(MSG_AUTH_SUCCESS)
            return ConversationHandler.END
            
        except Exception as e:
            await update.message.reply_text(f"خطا: ممکن است این نام قبلا ثبت شده باشد. \n{str(e)}")
            return AUTH_NAME
            
    else:
        await update.message.reply_text(MSG_AUTH_FAIL)
        return AUTH_NAME

def setup_handlers(application: Application):
    # Main Conversation for Auth
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            AUTH_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, auth_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Admin Conversation
    # Since admin commands start from a CallbackQuery in a menu usually, but here we mixed command and callback.
    # We'll make a separate ConversationHandler for admin actions triggered by Callbacks?
    # Actually, simpler to just have one ConversationHandler if we can help it, or separate.
    # The `admin_broadcast` returns a state. This requires an EntryPoint that returns that state.
    # But `admin_callback` is a CallbackQueryHandler, which is valid as an entry point!
    
    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback, pattern='^admin_')],
        states={
            ADMIN_BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_msg)],
            ADMIN_ADD_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_user_handler)],
            ADMIN_REMOVE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_remove_user_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True
    )

    application.add_handler(conv_handler)
    application.add_handler(admin_conv) 
    
    # Handlers that shouldn't be blocked by conversation?
    # Note: If admin_conv is active, it captures input. 
    
    application.add_handler(MessageHandler(filters.Document.MimeType("text/csv") | filters.Document.MimeType("text/comma-separated-values"), handle_document))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("rank", my_rank))
    application.add_handler(CommandHandler("help", help_command))
    
    # The /admin command just shows the menu. The menu clicks trigger the conversation.
    application.add_handler(CommandHandler("admin", admin_panel))
