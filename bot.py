import json
import os
import jdatetime
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

TOKEN = os.getenv("BOT_TOKEN")
DATA_FILE = "data.json"

# حالت‌ها
WAITING_ENTRY_TIME, WAITING_EXIT_TIME, WAITING_EXPENSE_DESC, WAITING_EXPENSE_AMOUNT = range(4)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_jalali_date():
    return jdatetime.date.today().strftime("%Y/%m/%d")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("ثبت ورود"), KeyboardButton("ثبت خروج")],
        [KeyboardButton("ثبت هزینه")],
        [KeyboardButton("دریافت اکسل ساعات"), KeyboardButton("دریافت اکسل هزینه‌ها")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "سلام! 👋\nربات مدیریت ساعات کاری و هزینه‌ها\nیکی از دکمه‌ها رو انتخاب کن:",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        data[user_id] = {"hours": [], "expenses": []}

    if text == "ثبت ورود":
        await update.message.reply_text("ساعت ورود رو بنویس (مثال: 08:30)")
        return WAITING_ENTRY_TIME

    elif text == "ثبت خروج":
        await update.message.reply_text("ساعت خروج رو بنویس (مثال: 17:45)")
        return WAITING_EXIT_TIME

    elif text == "ثبت هزینه":
        await update.message.reply_text("توضیحات هزینه رو بنویس:")
        return WAITING_EXPENSE_DESC

    elif text == "دریافت اکسل ساعات":
        await send_excel_hours(update, data, user_id)

    elif text == "دریافت اکسل هزینه‌ها":
        await send_excel_expenses(update, data, user_id)

    else:
        await update.message.reply_text("لطفاً از دکمه‌ها استفاده کن.")

    return ConversationHandler.END

async def entry_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = {"hours": [], "expenses": []}

    time = update.message.text.strip()
    data[user_id]["hours"].append({
        "date": get_jalali_date(),
        "entry": time,
        "exit": "",
        "duration": ""
    })
    save_data(data)
    await update.message.reply_text(f"✅ ورود ثبت شد: {time}")
    return ConversationHandler.END

async def exit_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data or not data[user_id]["hours"]:
        await update.message.reply_text("اول باید ورود ثبت کرده باشی.")
        return ConversationHandler.END

    # پیدا کردن آخرین رکورد بدون خروج
    last = None
    for h in reversed(data[user_id]["hours"]):
        if h["exit"] == "":
            last = h
            break

    if last is None:
        await update.message.reply_text("ورود باز برای ثبت خروج پیدا نشد.")
        return ConversationHandler.END

    time = update.message.text.strip()
    last["exit"] = time
    save_data(data)
    await update.message.reply_text(f"✅ خروج ثبت شد: {time}")
    return ConversationHandler.END

async def expense_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["expense_desc"] = update.message.text
    await update.message.reply_text("مبلغ هزینه رو به عدد بنویس (مثال: 50000):")
    return WAITING_EXPENSE_AMOUNT

async def expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = {"hours": [], "expenses": []}

    amount = update.message.text.replace(",", "").replace("٬", "").strip()
    data[user_id]["expenses"].append({
        "date": get_jalali_date(),
        "description": context.user_data.get("expense_desc", ""),
        "amount": amount
    })
    save_data(data)
    await update.message.reply_text("✅ هزینه با موفقیت ثبت شد.")
    return ConversationHandler.END

async def send_excel_hours(update: Update, data, user_id):
    hours = data.get(user_id, {}).get("hours", [])
    if not hours:
        await update.message.reply_text("هنوز ساعتی ثبت نشده.")
        return

    df = pd.DataFrame(hours)
    # مرتب کردن ستون‌ها
    df = df[["date", "entry", "exit", "duration"]]
    df.columns = ["تاریخ", "ورود", "خروج", "مدت"]
    
    file_name = f"hours_{user_id}.xlsx"
    df.to_excel(file_name, index=False, sheet_name="ساعات_کاری")
    
    with open(file_name, "rb") as f:
        await update.message.reply_document(document=f, filename="ساعات_کاری.xlsx")
    os.remove(file_name)

async def send_excel_expenses(update: Update, data, user_id):
    expenses = data.get(user_id, {}).get("expenses", [])
    if not expenses:
        await update.message.reply_text("هنوز هزینه‌ای ثبت نشده.")
        return

    df = pd.DataFrame(expenses)
    df = df[["date", "description", "amount"]]
    df.columns = ["تاریخ", "توضیحات", "مبلغ"]
    
    file_name = f"expenses_{user_id}.xlsx"
    df.to_excel(file_name, index=False, sheet_name="هزینه‌ها")
    
    with open(file_name, "rb") as f:
        await update.message.reply_document(document=f, filename="هزینه‌ها.xlsx")
    os.remove(file_name)

def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        states={
            WAITING_ENTRY_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, entry_time)],
            WAITING_EXIT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, exit_time)],
            WAITING_EXPENSE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_desc)],
            WAITING_EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_amount)],
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    print("ربات شروع به کار کرد...")
    app.run_polling()

if __name__ == "__main__":
    main()
