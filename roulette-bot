import os
import random
import asyncio

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery


BOT_TOKEN = os.getenv("8541453435:AAEqXEyRE46CydJBPMPoKc87YwmCAHZWP54")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN تنظیم نشده است.")


app = Client(
    "roulette_bot",
    bot_token=BOT_TOKEN
)


games = {}


def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎰 شروع بازی", callback_data="start")
        ],
        [
            InlineKeyboardButton("📖 راهنما", callback_data="help")
        ]
    ])


@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "🎰 **رولت شانس**\n\n"
        "یک بازی کاملاً مجازی و تصادفی است.\n"
        "برای شروع روی دکمه زیر بزن:",
        reply_markup=main_menu()
    )


@app.on_callback_query(filters.regex("^start$"))
async def start_game(client, callback: CallbackQuery):

    user_id = callback.from_user.id

    # عدد تصادفی برای بازی
    lucky_number = random.randint(1, 6)

    games[user_id] = lucky_number

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 شانس من", callback_data="roll")
        ],
        [
            InlineKeyboardButton("🔙 برگشت", callback_data="back")
        ]
    ])

    await callback.message.edit_text(
        "🎰 **بازی جدید شروع شد!**\n\n"
        "یک عدد مخفی بین ۱ تا ۶ انتخاب شده.\n\n"
        "آماده‌ای شانس خودت را امتحان کنی؟ 😈",
        reply_markup=keyboard
    )

    await callback.answer()


@app.on_callback_query(filters.regex("^roll$"))
async def roll(client, callback: CallbackQuery):

    user_id = callback.from_user.id

    if user_id not in games:
        await callback.answer(
            "اول یک بازی جدید شروع کن!",
            show_alert=True
        )
        return

    await callback.message.edit_text("🎲 در حال انتخاب عدد...\n\n⏳")
    await asyncio.sleep(1)

    user_number = random.randint(1, 6)
    lucky_number = games[user_id]

    if user_number == lucky_number:

        result = (
            "💥 **باختی!**\n\n"
            f"عدد تو: `{user_number}`\n"
            f"عدد مخفی: `{lucky_number}`\n\n"
            "😈 این دور شانست یاری نکرد!"
        )

    else:

        result = (
            "🟢 **بردی!**\n\n"
            f"عدد تو: `{user_number}`\n"
            f"عدد مخفی: `{lucky_number}`\n\n"
            "🔥 شانس با تو بود!"
        )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎰 بازی دوباره", callback_data="start")
        ],
        [
            InlineKeyboardButton("🏠 منوی اصلی", callback_data="back")
        ]
    ])

    await callback.message.edit_text(
        result,
        reply_markup=keyboard
    )

    del games[user_id]

    await callback.answer()


@app.on_callback_query(filters.regex("^back$"))
async def back(client, callback: CallbackQuery):

    await callback.message.edit_text(
        "🎰 **رولت شانس**\n\n"
        "یک بازی کاملاً مجازی و تصادفی.\n\n"
        "برای شروع بازی روی دکمه زیر بزن:",
        reply_markup=main_menu()
    )

    await callback.answer()


@app.on_callback_query(filters.regex("^help$"))
async def help_menu(client, callback: CallbackQuery):

    await callback.message.edit_text(
        "📖 **راهنمای بازی**\n\n"
        "🎰 بازی کاملاً مجازی است.\n"
        "🎲 سیستم به‌صورت تصادفی نتیجه را تعیین می‌کند.\n"
        "🏆 اگر عدد انتخابی متفاوت باشد، برنده می‌شوی.\n"
        "💥 اگر یکسان باشد، آن دور را می‌بازی.\n\n"
        "برای برگشت به منوی اصلی:",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔙 برگشت", callback_data="back")
            ]
        ])
    )

    await callback.answer()


print("🤖 Bot is running...")

app.run()
