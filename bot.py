import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import (
    PhoneInvalid, 
    PhoneCodeInvalid, 
    PhoneCodeExpired,
    SessionPasswordNeeded,
    FloodWait,
    BadRequest
)
from pyrogram.enums import ChatType
import time

# تنظیمات لاگینگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# خواندن متغیرهای محیطی
API_ID = int(os.environ.get("34855392
", 0))
API_HASH = os.environ.get("5e40d435847009c31c24042e2a3c0d3b", "")
BOT_TOKEN = os.environ.get("8692323102:AAHVQ5sxZjQk81D8YN5QNItQXMt25vurXqQ", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise ValueError("API_ID, API_HASH و BOT_TOKEN باید در متغیرهای محیطی تنظیم شوند!")

# دیکشنری برای نگهداری وضعیت کاربران
user_sessions = {}

# کلاس مدیریت وضعیت کاربر
class UserState:
    def __init__(self, user_id):
        self.user_id = user_id
        self.phone = None
        self.phone_code_hash = None
        self.step = "start"  # start, phone, code, password, done, cancelled
        self.client = None
        self.session_name = None
        self.is_2fa = False
        self.temp_client = None
        
    def reset(self):
        self.phone = None
        self.phone_code_hash = None
        self.step = "start"
        if self.client:
            try:
                self.client.stop()
            except:
                pass
            self.client = None
        self.session_name = None
        self.is_2fa = False
        self.temp_client = None

# ربات اصلی
app = Client(
    "auth_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

def get_user_state(user_id):
    """دریافت یا ایجاد وضعیت برای کاربر"""
    if user_id not in user_sessions:
        user_sessions[user_id] = UserState(user_id)
    return user_sessions[user_id]

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    """دستور شروع - مرحله 1"""
    user_id = message.from_user.id
    state = get_user_state(user_id)
    state.reset()
    state.step = "phone"
    
    await message.reply_text(
        "🤖 **به ربات ساخت Session خوش آمدید!**\n\n"
        "📱 لطفاً شماره تلفن اکانت تلگرام خود را ارسال کنید.\n"
        "مثال: `+989123456789`\n\n"
        "⚠️ برای لغو فرایند، دستور `/cancel` را ارسال کنید."
    )

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_command(client, message):
    """لغو فرایند - مرحله 7"""
    user_id = message.from_user.id
    if user_id in user_sessions:
        state = user_sessions[user_id]
        if state.temp_client:
            try:
                await state.temp_client.stop()
            except:
                pass
        state.reset()
        del user_sessions[user_id]
    
    await message.reply_text(
        "❌ **فرایند لغو شد.**\n\n"
        "برای شروع مجدد، دستور `/start` را ارسال کنید."
    )

@app.on_message(filters.text & filters.private & ~filters.command(["start", "cancel"]))
async def handle_messages(client, message):
    """مدیریت پیام‌های متنی - مراحل 2 تا 6"""
    user_id = message.from_user.id
    text = message.text.strip()
    
    if user_id not in user_sessions:
        await message.reply_text("لطفاً ابتدا با دستور `/start` شروع کنید.")
        return
    
    state = user_sessions[user_id]
    
    try:
        if state.step == "phone":
            await handle_phone(client, message, state, text)
        elif state.step == "code":
            await handle_code(client, message, state, text)
        elif state.step == "password":
            await handle_password(client, message, state, text)
        else:
            await message.reply_text("⚠️ وضعیت نامعتبر. لطفاً با `/start` شروع کنید.")
            state.reset()
            
    except Exception as e:
        logger.error(f"خطا در پردازش پیام از {user_id}: {e}")
        await message.reply_text(
            f"❌ خطایی رخ داد: `{str(e)}`\n\n"
            "لطفاً با `/start` دوباره تلاش کنید."
        )
        state.reset()

async def handle_phone(client, message, state, phone):
    """مرحله 2: دریافت شماره تلفن"""
    # اعتبارسنجی شماره
    if not phone.startswith('+') or not phone[1:].isdigit():
        await message.reply_text(
            "❌ **شماره نامعتبر!**\n\n"
            "لطفاً شماره را با فرمت بین‌المللی ارسال کنید:\n"
            "مثال: `+989123456789`"
        )
        return
    
    try:
        # ایجاد کلاینت موقت برای احراز هویت
        session_name = f"session_{state.user_id}_{int(time.time())}"
        state.session_name = session_name
        
        temp_client = Client(
            session_name,
            api_id=API_ID,
            api_hash=API_HASH,
            in_memory=True  # استفاده از حافظه برای جلوگیری از ذخیره فایل موقت
        )
        state.temp_client = temp_client
        
        await temp_client.connect()
        
        # ارسال درخواست کد
        sent_code = await temp_client.send_code(phone)
        state.phone = phone
        state.phone_code_hash = sent_code.phone_code_hash
        state.step = "code"
        
        await message.reply_text(
            "✅ **کد تأیید ارسال شد!**\n\n"
            "📨 کد 5 رقمی ارسال‌شده به تلگرام خود را وارد کنید.\n"
            "کد را به این شکل بفرستید:\n"
            "`5 5 5 5 5`\n\n"
            "⚠️ کد معتبر تا چند دقیقه است."
        )
        
    except PhoneInvalid:
        await message.reply_text(
            "❌ **شماره نامعتبر!**\n\n"
            "لطفاً شماره معتبر تلگرام را با فرمت بین‌المللی ارسال کنید."
        )
        state.reset()
    except FloodWait as e:
        await message.reply_text(
            f"⏳ **صبر کنید!**\n\n"
            f"لطفاً {e.value} ثانیه صبر کنید و دوباره تلاش کنید."
        )
    except Exception as e:
        logger.error(f"خطا در ارسال کد: {e}")
        await message.reply_text(
            f"❌ **خطا در ارسال کد!**\n\n"
            f"خطا: `{str(e)}`\n"
            "لطفاً با `/start` دوباره تلاش کنید."
        )
        state.reset()

async def handle_code(client, message, state, code):
    """مرحله 3 و 4: دریافت و تأیید کد"""
    # حذف فاصله‌ها از کد
    code = code.replace(" ", "").strip()
    
    if not code.isdigit() or len(code) != 5:
        await message.reply_text(
            "❌ **کد نامعتبر!**\n\n"
            "لطفاً کد 5 رقمی را به این شکل وارد کنید:\n"
            "`5 5 5 5 5` یا `55555`"
        )
        return
    
    try:
        # تأیید کد
        await state.temp_client.sign_in(
            state.phone,
            state.phone_code_hash,
            code
        )
        
        # اگر به اینجا رسید، ورود موفق بود
        state.step = "done"
        
        # دریافت اطلاعات کاربر
        me = await state.temp_client.get_me()
        
        # ساخت Session String
        session_string = await state.temp_client.export_session_string()
        
        # ذخیره Session در فایل
        session_file = f"{state.session_name}.session"
        with open(session_file, "w") as f:
            f.write(session_string)
        
        # ارسال فایل به کاربر - مرحله 10
        await message.reply_document(
            document=session_file,
            caption=f"✅ **ساخت Session با موفقیت انجام شد!**\n\n"
                   f"👤 کاربر: {me.first_name} (@{me.username if me.username else 'ندارد'})\n"
                   f"📱 شماره: {state.phone}\n"
                   f"🆔 آیدی: {me.id}\n\n"
                   f"🔐 این فایل برای اجرای کد اصلی شما ضروری است."
        )
        
        # مرحله 11: پیام موفقیت
        await message.reply_text(
            "🎉 **فرایند با موفقیت کامل شد!**\n\n"
            "✅ فایل Session ساخته و ارسال شد.\n"
            "📁 فایل روی سرور نیز ذخیره شده است.\n\n"
            "💡 برای استفاده از این Session در کد اصلی خود، فایل را در مسیر مناسب قرار دهید."
        )
        
        # پاک کردن فایل موقت پس از ارسال - مرحله 10
        try:
            os.remove(session_file)
        except:
            pass
            
        # بستن کلاینت موقت
        await state.temp_client.stop()
        state.reset()
        
    except PhoneCodeInvalid:
        await message.reply_text(
            "❌ **کد اشتباه است!**\n\n"
            "لطفاً کد صحیح را وارد کنید.\n"
            "اگر کد را دریافت نکردید، با `/start` دوباره تلاش کنید."
        )
    except PhoneCodeExpired:
        await message.reply_text(
            "❌ **کد منقضی شده!**\n\n"
            "لطفاً با `/start` دوباره تلاش کنید."
        )
    except SessionPasswordNeeded:
        # مرحله 6: نیاز به رمز 2FA
        state.is_2fa = True
        state.step = "password"
        await message.reply_text(
            "🔐 **احراز هویت دو مرحله‌ای فعال است!**\n\n"
            "لطفاً رمز عبور دومرحله‌ای خود را وارد کنید."
        )
    except FloodWait as e:
        await message.reply_text(
            f"⏳ **صبر کنید!**\n\n"
            f"لطفاً {e.value} ثانیه صبر کنید و دوباره تلاش کنید."
        )
    except Exception as e:
        logger.error(f"خطا در تأیید کد: {e}")
        await message.reply_text(
            f"❌ **خطا در تأیید کد!**\n\n"
            f"خطا: `{str(e)}`\n"
            "لطفاً با `/start` دوباره تلاش کنید."
        )
        state.reset()

async def handle_password(client, message, state, password):
    """مرحله 6: دریافت رمز 2FA"""
    try:
        # تأیید رمز 2FA
        await state.temp_client.check_password(password)
        
        # ورود موفق
        state.step = "done"
        
        # دریافت اطلاعات کاربر
        me = await state.temp_client.get_me()
        
        # ساخت Session String
        session_string = await state.temp_client.export_session_string()
        
        # ذخیره Session در فایل
        session_file = f"{state.session_name}.session"
        with open(session_file, "w") as f:
            f.write(session_string)
        
        # ارسال فایل به کاربر
        await message.reply_document(
            document=session_file,
            caption=f"✅ **ساخت Session با موفقیت انجام شد!**\n\n"
                   f"👤 کاربر: {me.first_name} (@{me.username if me.username else 'ندارد'})\n"
                   f"📱 شماره: {state.phone}\n"
                   f"🆔 آیدی: {me.id}\n\n"
                   f"🔐 این فایل برای اجرای کد اصلی شما ضروری است."
        )
        
        # پیام موفقیت
        await message.reply_text(
            "🎉 **فرایند با موفقیت کامل شد!**\n\n"
            "✅ فایل Session ساخته و ارسال شد.\n"
            "📁 فایل روی سرور نیز ذخیره شده است."
        )
        
        # پاک کردن فایل موقت
        try:
            os.remove(session_file)
        except:
            pass
            
        # بستن کلاینت موقت
        await state.temp_client.stop()
        state.reset()
        
    except BadRequest:
        await message.reply_text(
            "❌ **رمز عبور اشتباه است!**\n\n"
            "لطفاً رمز صحیح را وارد کنید."
        )
    except FloodWait as e:
        await message.reply_text(
            f"⏳ **صبر کنید!**\n\n"
            f"لطفاً {e.value} ثانیه صبر کنید و دوباره تلاش کنید."
        )
    except Exception as e:
        logger.error(f"خطا در تأیید رمز 2FA: {e}")
        await message.reply_text(
            f"❌ **خطا در تأیید رمز!**\n\n"
            f"خطا: `{str(e)}`\n"
            "لطفاً با `/start` دوباره تلاش کنید."
        )
        state.reset()

@app.on_message(filters.command("help") & filters.private)
async def help_command(client, message):
    """دستور راهنما"""
    await message.reply_text(
        "🤖 **راهنمای ربات ساخت Session**\n\n"
        "🔹 `/start` - شروع فرایند ساخت Session\n"
        "🔹 `/cancel` - لغو فرایند جاری\n"
        "🔹 `/help` - نمایش این راهنما\n\n"
        "📌 **مراحل:**\n"
        "1️⃣ شماره تلفن خود را ارسال کنید\n"
        "2️⃣ کد تأیید ارسال‌شده به تلگرام را وارد کنید\n"
        "3️⃣ در صورت نیاز، رمز 2FA را وارد کنید\n"
        "4️⃣ فایل Session ساخته و برای شما ارسال می‌شود\n\n"
        "⚠️ **توجه:** فایل Session به شما امکان دسترسی به حساب تلگرام را می‌دهد. آن را با کسی به اشتراک نگذارید."
    )

async def main():
    """تابع اصلی اجرا"""
    try:
        logger.info("ربات در حال اجرا...")
        await app.start()
        logger.info("ربات با موفقیت شروع به کار کرد!")
        await asyncio.Event().wait()  # منتظر ماندن برای همیشه
    except KeyboardInterrupt:
        logger.info("ربات متوقف شد.")
    except Exception as e:
        logger.error(f"خطا در اجرای ربات: {e}")
    finally:
        # پاکسازی منابع
        for user_id, state in list(user_sessions.items()):
            try:
                if state.temp_client:
                    await state.temp_client.stop()
                state.reset()
            except:
                pass
        user_sessions.clear()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
