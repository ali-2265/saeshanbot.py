
# ===== Config.py =====

import os

ENVIRONMENT = os.getenv("ENVIRONMENT", "true").lower() == "true"

try:
    API_ID = int(os.getenv("API_ID", "0"))
except ValueError:
    raise RuntimeError("API_ID باید عدد باشد.")

API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("8541453435:AAEqXEyRE46CydJBPMPoKc87YwmCAHZWP54", "")
MUST_JOIN = os.getenv("MUST_JOIN", "").lstrip("@")

# اگر DATABASE_URL تنظیم نشده باشد، از SQLite محلی استفاده می‌شود.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///users.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise RuntimeError("API_ID، API_HASH و BOT_TOKEN را در Environment Variables تنظیم کنید.")


# ===== Data.py =====

from pyrogram.types import InlineKeyboardButton


class Data:
    START = """
سلام {}

این ربات برای ساخت Session String در Pyrogram و Telethon طراحی شده است.

⚠️ Session String اطلاعات بسیار حساس حساب تلگرام است.
آن را با هیچ شخص یا ربات دیگری به اشتراک نگذارید.

سازنده: @zenfrans
"""

    home_buttons = [
        [InlineKeyboardButton("🔐 ساخت Session", callback_data="generate")],
        [InlineKeyboardButton("🏠 خانه", callback_data="home")],
    ]

    generate_button = [
        [InlineKeyboardButton("🔐 شروع ساخت Session", callback_data="generate")]
    ]

    buttons = [
        [InlineKeyboardButton("🔐 ساخت Session", callback_data="generate")],
        [InlineKeyboardButton("👤 سازنده", url="https://t.me/zenfrans")],
        [
            InlineKeyboardButton("❓ راهنما", callback_data="help"),
            InlineKeyboardButton("ℹ️ درباره", callback_data="about"),
        ],
    ]

    HELP = """
✨ راهنمای ربات ✨

/start — شروع ربات
/generate — شروع ساخت Session
/help — نمایش راهنما
/about — درباره ربات
/cancel — لغو عملیات
/restart — شروع دوباره

⚠️ اطلاعات ورود، کد تأیید و Session String را در اختیار دیگران قرار ندهید.
"""

    ABOUT = """
ℹ️ درباره ربات

این ربات برای ساخت Session String مربوط به Pyrogram و Telethon طراحی شده است.

⚠️ Session String مانند اطلاعات ورود حساس حساب است.
آن را در GitHub عمومی، گروه یا برای افراد دیگر ارسال نکنید.

Framework: Pyrogram / Telethon
Language: Python
"""


# ===== StringSessionBot/database/__init__.py =====

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker
from Config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)
BASE = declarative_base()
BASE.metadata.bind = engine

SESSION = scoped_session(
    sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
)


# ===== StringSessionBot/database/users_sql.py =====

from sqlalchemy import Column, Integer
from database import BASE, SESSION


class Users(BASE):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    user_id = Column(Integer, primary_key=True)

    def __init__(self, user_id):
        self.user_id = user_id


BASE.metadata.create_all(bind=SESSION.bind)


async def num_users():
    try:
        return SESSION.query(Users).count()
    finally:
        SESSION.remove()


# ===== StringSessionBot/generate.py =====

from asyncio.exceptions import TimeoutError

from Data import Data
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid,
)
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    ApiIdInvalidError,
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
    PasswordHashInvalidError,
)

ERROR_MESSAGE = (
    "❌ خطایی رخ داد!\n\n"
    "**خطا:** {}\n\n"
    "اگر خطا تکرار شد، از اجرای دوباره عملیات خودداری کنید."
)


@Client.on_message(filters.private & ~filters.forwarded & filters.command("generate"))
async def main(_, msg):
    await msg.reply(
        "لطفاً نوع Session را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("Pyrogram", callback_data="pyrogram"),
                InlineKeyboardButton("Telethon", callback_data="telethon"),
            ]]
        ),
    )


async def generate_session(bot, msg, telethon=False):
    await msg.reply(
        f"🔄 شروع ساخت Session برای {'Telethon' if telethon else 'Pyrogram'}..."
    )

    user_id = msg.chat.id

    api_id_msg = await bot.ask(
        user_id, "لطفاً `API_ID` خود را وارد کنید.", filters=filters.text, timeout=300
    )
    if await cancelled(api_id_msg):
        return

    try:
        api_id = int(api_id_msg.text.strip())
    except ValueError:
        await api_id_msg.reply(
            "❌ API_ID باید یک عدد باشد.",
            quote=True,
            reply_markup=InlineKeyboardMarkup(Data.generate_button),
        )
        return

    api_hash_msg = await bot.ask(
        user_id, "لطفاً `API_HASH` خود را وارد کنید.", filters=filters.text, timeout=300
    )
    if await cancelled(api_hash_msg):
        return
    api_hash = api_hash_msg.text.strip()

    phone_number_msg = await bot.ask(
        user_id,
        "لطفاً شماره تلفن حساب را با کد کشور وارد کنید.\nمثال: `+937XXXXXXXX`",
        filters=filters.text,
        timeout=300,
    )
    if await cancelled(phone_number_msg):
        return
    phone_number = phone_number_msg.text.strip()

    await msg.reply("📨 درخواست کد تأیید ارسال شد.")

    if telethon:
        client = TelegramClient(StringSession(), api_id, api_hash)
    else:
        client = Client(":memory:", api_id, api_hash)

    await client.connect()

    try:
        if telethon:
            sent_code = await client.send_code_request(phone_number)
        else:
            sent_code = await client.send_code(phone_number)
    except (ApiIdInvalid, ApiIdInvalidError):
        await client.disconnect()
        await msg.reply(
            "❌ ترکیب API_ID و API_HASH نادرست است.",
            reply_markup=InlineKeyboardMarkup(Data.generate_button),
        )
        return
    except (PhoneNumberInvalid, PhoneNumberInvalidError):
        await client.disconnect()
        await msg.reply(
            "❌ شماره تلفن نادرست است.",
            reply_markup=InlineKeyboardMarkup(Data.generate_button),
        )
        return

    try:
        phone_code_msg = await bot.ask(
            user_id,
            "📩 کد تأیید را در حساب رسمی تلگرام بررسی کنید.\n"
            "کد را با فاصله وارد کنید؛ مثال: `1 2 3 4 5`.",
            filters=filters.text,
            timeout=600,
        )
    except TimeoutError:
        await client.disconnect()
        await msg.reply(
            "⏰ زمان ۱۰ دقیقه‌ای تمام شد.",
            reply_markup=InlineKeyboardMarkup(Data.generate_button),
        )
        return

    if await cancelled(phone_code_msg):
        await client.disconnect()
        return

    phone_code = phone_code_msg.text.replace(" ", "").strip()

    try:
        if telethon:
            await client.sign_in(
                phone=phone_number,
                code=phone_code,
                phone_code_hash=sent_code.phone_code_hash,
            )
        else:
            await client.sign_in(
                phone_number,
                sent_code.phone_code_hash,
                phone_code,
            )
    except (PhoneCodeInvalid, PhoneCodeInvalidError):
        await client.disconnect()
        await msg.reply(
            "❌ کد تأیید نادرست است.",
            reply_markup=InlineKeyboardMarkup(Data.generate_button),
        )
        return
    except (PhoneCodeExpired, PhoneCodeExpiredError):
        await client.disconnect()
        await msg.reply(
            "❌ کد تأیید منقضی شده است.",
            reply_markup=InlineKeyboardMarkup(Data.generate_button),
        )
        return
    except (SessionPasswordNeeded, SessionPasswordNeededError):
        try:
            two_step_msg = await bot.ask(
                user_id,
                "🔐 تأیید دومرحله‌ای فعال است. رمز دو مرحله‌ای را وارد کنید.",
                filters=filters.text,
                timeout=300,
            )
        except TimeoutError:
            await client.disconnect()
            await msg.reply(
                "⏰ زمان ۵ دقیقه‌ای تمام شد.",
                reply_markup=InlineKeyboardMarkup(Data.generate_button),
            )
            return

        if await cancelled(two_step_msg):
            await client.disconnect()
            return

        try:
            password = two_step_msg.text
            if telethon:
                await client.sign_in(password=password)
            else:
                await client.check_password(password=password)
        except (PasswordHashInvalid, PasswordHashInvalidError):
            await client.disconnect()
            await two_step_msg.reply(
                "❌ رمز واردشده نادرست است.",
                quote=True,
                reply_markup=InlineKeyboardMarkup(Data.generate_button),
            )
            return

    if telethon:
        string_session = client.session.save()
    else:
        string_session = await client.export_session_string()

    # Session را فقط برای صاحب حساب ارسال می‌کنیم.
    text = (
        f"**{'TELETHON' if telethon else 'PYROGRAM'} STRING SESSION**\n\n"
        f"`{string_session}`\n\n"
        "⚠️ این Session را محرمانه نگه دارید."
    )

    await msg.reply(
        "✅ Session با موفقیت ساخته شد.\n\n"
        "⚠️ Session را با هیچ‌کس به اشتراک نگذارید."
    )
    await msg.reply(text)
    await client.disconnect()


async def cancelled(msg):
    text = (msg.text or "").strip()

    if text == "/cancel":
        await msg.reply(
            "❌ عملیات لغو شد.",
            quote=True,
            reply_markup=InlineKeyboardMarkup(Data.generate_button),
        )
        return True

    if text == "/restart":
        await msg.reply(
            "🔄 عملیات دوباره شروع شد.",
            quote=True,
            reply_markup=InlineKeyboardMarkup(Data.generate_button),
        )
        return True

    if text.startswith("/"):
        await msg.reply("❌ عملیات ساخت Session لغو شد.", quote=True)
        return True

    return False


# ===== StringSessionBot/start.py =====

from Data import Data
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup


@Client.on_message(filters.private & filters.incoming & filters.command("start"))
async def start(bot, msg):
    user = await bot.get_me()
    mention = user.mention
    await bot.send_message(
        msg.chat.id,
        Data.START.format(msg.from_user.mention, mention),
        reply_markup=InlineKeyboardMarkup(Data.buttons),
    )


# ===== StringSessionBot/callbacks.py =====

from Data import Data
from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
# generate_session and ERROR_MESSAGE are defined above


@Client.on_callback_query()
async def _callbacks(bot: Client, callback_query: CallbackQuery):
    user = await bot.get_me()
    mention = user.mention
    query = (callback_query.data or "").lower()

    if query == "home":
        await callback_query.message.edit_text(
            Data.START.format(callback_query.from_user.mention, mention),
            reply_markup=InlineKeyboardMarkup(Data.buttons),
        )

    elif query == "about":
        await callback_query.message.edit_text(
            Data.ABOUT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(Data.home_buttons),
        )

    elif query == "help":
        await callback_query.message.edit_text(
            "**روش استفاده از ربات:**\n" + Data.HELP,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(Data.home_buttons),
        )

    elif query == "generate":
        await callback_query.answer()
        await callback_query.message.reply(
            "لطفاً نوع Session را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Pyrogram", callback_data="pyrogram"),
                InlineKeyboardButton("Telethon", callback_data="telethon"),
            ]]),
        )

    elif query in ("pyrogram", "telethon"):
        await callback_query.answer()
        try:
            await generate_session(
                bot,
                callback_query.message,
                telethon=(query == "telethon"),
            )
        except Exception as e:
            await callback_query.message.reply(ERROR_MESSAGE.format(str(e)))


# ===== StringSessionBot/help.py =====

from Data import Data
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup


@Client.on_message(filters.private & filters.incoming & filters.command("help"))
async def _help(bot, msg):
    await bot.send_message(
        msg.chat.id,
        "**روش استفاده از ربات:**\n" + Data.HELP,
        reply_markup=InlineKeyboardMarkup(Data.home_buttons),
    )


# ===== StringSessionBot/about.py =====

from Data import Data
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup


@Client.on_message(filters.private & filters.incoming & filters.command("about"))
async def about(bot, msg):
    await bot.send_message(
        msg.chat.id,
        Data.ABOUT,
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(Data.home_buttons),
    )


# ===== StringSessionBot/must_join.py =====

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import ChatAdminRequired, UserNotParticipant, ChatWriteForbidden
from Config import MUST_JOIN


@Client.on_message(~filters.edited & filters.incoming & filters.private, group=-1)
async def must_join_channel(bot: Client, msg: Message):
    if not MUST_JOIN:
        return

    try:
        try:
            await bot.get_chat_member(MUST_JOIN, msg.from_user.id)
        except UserNotParticipant:
            chat = await bot.get_chat(MUST_JOIN)
            link = chat.invite_link or f"https://t.me/{MUST_JOIN}"

            try:
                await msg.reply(
                    f"برای استفاده از ربات باید ابتدا در [این کانال]({link}) عضو شوید.",
                    disable_web_page_preview=True,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("✨ عضویت در کانال ✨", url=link)]]
                    ),
                )
                await msg.stop_propagation()
            except ChatWriteForbidden:
                pass
    except ChatAdminRequired:
        print(f"ربات در کانال/گروه اجباری مدیر نیست: {MUST_JOIN}")


# ===== StringSessionBot/database/users.py =====

from pyrogram import Client, filters
from pyrogram.types import Message
from database_users_sql import Users
from database import SESSION


@Client.on_message(~filters.edited & ~filters.service, group=1)
async def users_sql(_, msg: Message):
    if not msg.from_user:
        return

    try:
        user_id = int(msg.from_user.id)
        q = SESSION.query(Users).filter(Users.user_id == user_id).first()

        if not q:
            SESSION.add(Users(user_id))
            SESSION.commit()
    finally:
        SESSION.remove()


@Client.on_message(filters.user(1938466384) & ~filters.edited & filters.command("stats"))
async def _stats(_, msg: Message):
    from StringSessionBot.database.users_sql import num_users
    users = await num_users()
    await msg.reply(f"تعداد کاربران: {users}", quote=True)


# ===== RUN =====
if __name__ == "__main__":
    try:
        app.start()
    except (ApiIdInvalid, ApiIdPublishedFlood):
        raise RuntimeError("❌ API_ID یا API_HASH نادرست است.")
    except AccessTokenInvalid:
        raise RuntimeError("❌ BOT_TOKEN نادرست است.")

    me = app.get_me()
    print(f"✅ ربات @{me.username} با موفقیت اجرا شد.")

    try:
        idle()
    finally:
        app.stop()
        print("🛑 ربات متوقف شد.")
