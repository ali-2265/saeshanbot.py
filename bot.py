import os
import asyncio

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set")


# ذخیره موقت سورس هر کاربر
user_sources = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    user_sources[user_id] = []

    await update.message.reply_text(
        "✅ حالت دریافت سورس فعال شد.\n\n"
        "هر خط از کد را جداگانه ارسال کن.\n"
        "مثال:\n\n"
        "5\n"
        "5\n"
        "5\n"
        "5\n\n"
        "هر پیام = یک خط از سورس\n\n"
        "برای پایان دریافت:\n"
        "/done\n\n"
        "برای لغو:\n"
        "/cancel"
    )


async def receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # اگر کاربر در حالت دریافت سورس نباشد
    if user_id not in user_sources:
        return

    text = update.message.text

    # ذخیره دقیق همان خط
    user_sources[user_id].append(text)

    line_number = len(user_sources[user_id])

    await update.message.reply_text(
        f"✅ خط {line_number} دریافت شد."
    )


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_sources:
        await update.message.reply_text(
            "❌ در حال حاضر سورسی برای دریافت وجود ندارد.\n"
            "ابتدا /start را بزن."
        )
        return

    lines = user_sources[user_id]

    if not lines:
        await update.message.reply_text(
            "❌ هنوز هیچ خطی دریافت نشده است."
        )
        return

    # ساخت سورس نهایی
    source_code = "\n".join(lines)

    filename = f"source_{user_id}.py"

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as file:
        file.write(source_code)

    # ارسال فایل
    try:
        with open(filename, "rb") as file:
            await update.message.reply_document(
                document=file,
                filename="source.py",
                caption=(
                    "✅ دریافت سورس تمام شد.\n\n"
                    f"تعداد خطوط: {len(lines)}"
                )
            )

    finally:
        # حذف اطلاعات موقت
        user_sources.pop(user_id, None)

        # حذف فایل ساخته‌شده
        if os.path.exists(filename):
            os.remove(filename)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in user_sources:
        user_sources.pop(user_id, None)

        await update.message.reply_text(
            "❌ دریافت سورس لغو شد."
        )
    else:
        await update.message.reply_text(
            "ℹ️ دریافت سورسی فعال نیست."
        )


async def main():

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # دستورات
    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("done", done)
    )

    application.add_handler(
        CommandHandler("cancel", cancel)
    )

    # دریافت خطوط کد
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_code
        )
    )

    print("Bot is running...")

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    try:
        while True:
            await asyncio.sleep(3600)

    except KeyboardInterrupt:
        pass

    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
