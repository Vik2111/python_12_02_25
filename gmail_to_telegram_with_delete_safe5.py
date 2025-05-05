# gmail_to_telegram_with_delete_safe5.py
import os
import imaplib
import email
import logging
from email.header import decode_header
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import asyncio

load_dotenv()

EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

seen_uids = set()
bot = Bot(token=TELEGRAM_TOKEN)

async def send_email(uid, from_, subject, date):
    msg = f"📨 От: {from_}\n📌 Тема: {subject}\n📅 Дата: {date}"
    button = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Удалить", callback_data=f"delete_{uid}")]
    ])
    await bot.send_message(chat_id=CHAT_ID, text=msg, reply_markup=button)

async def check_mail():
    try:
        with imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT) as imap:
            imap.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
            logging.info("✅ Успешный IMAP логин")
            imap.select("inbox")
            result, data = imap.search(None, "ALL")
            logging.info(f"🔍 Поиск писем: {result}")
            if result != "OK":
                return

            for num in data[0].split():
                if num in seen_uids:
                    continue
                seen_uids.add(num)
                res, msg_data = imap.fetch(num, "(RFC822)")
                if res != "OK":
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                from_ = decode_header(msg["From"])[0][0]
                subject = decode_header(msg["Subject"])[0][0]
                date = msg["Date"]
                if isinstance(from_, bytes):
                    from_ = from_.decode(errors="ignore")
                if isinstance(subject, bytes):
                    subject = subject.decode(errors="ignore")
                logging.info(f"📥 Найдено письмо UID={num.decode()}: {subject}")
                logging.info(f"📤 Представлено в Telegram: UID={num.decode()}, From={from_}, Subject={subject}")
                await send_email(num.decode(), from_, subject, date)
    except Exception as e:
        logging.error(f"💥 Ошибка при проверке почты: {e}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("delete_"):
        uid = query.data.split("_")[1]
        with imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT) as imap:
            imap.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
            logging.info("📩 Удаление: логин выполнен")
            imap.select("inbox")
            logging.info("📁 Выбрана папка inbox")
            result = imap.uid("STORE", uid, "+FLAGS", r"(\Deleted)")
            logging.info(f"🗑 STORE UID={uid} результат: {result[0]}")
            imap.expunge()
            logging.info(f"✅ Expunge для UID={uid} выполнен")
        await query.edit_message_text("✅ Письмо удалено.")

async def run():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CallbackQueryHandler(handle_callback))
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_mail, "interval", minutes=1)
    scheduler.start()
    logging.info("📲 Application started")
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    import asyncio
    asyncio.get_event_loop().run_until_complete(run())
