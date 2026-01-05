import os
import io
import logging
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

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    if not user or not user.is_admin:
        await update.message.reply_text(MSG_ADMIN_ONLY)
        return

    keyboard = [
        [InlineKeyboardButton("مدیریت کاربران (Coming Soon)", callback_data='admin_users')],
        [InlineKeyboardButton("خروجی اکسل (Coming Soon)", callback_data='admin_export')],
        [InlineKeyboardButton("بستن مسابقه (Coming Soon)", callback_data='admin_freeze')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("پنل مدیریت:", reply_markup=reply_markup)

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=f"گزینه انتخاب شد: {query.data} \n(این قابلیت هنوز پیاده‌سازی نشده است)")

def setup_handlers(application: Application):
    # Conversation for Auth
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            AUTH_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, auth_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.Document.MimeType("text/csv") | filters.Document.MimeType("text/comma-separated-values"), handle_document))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("rank", my_rank))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(admin_callback, pattern='^admin_'))
