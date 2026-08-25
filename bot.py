import os
import asyncio
import re

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
)
from telethon.tl.types import Message

# ==============================
# Telegram API
# ==============================

API_ID = 34855392
API_HASH = "YOUR_API_HASH"
BOT_TOKEN = "YOUR_BOT_TOKEN"  # توکن ربات خود را وارد کنید

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

user_sessions = {}  # {user_id: {"step": "waiting_phone", "phone": "..."}, ...}
user_data = {}      # {user_id: {"session_name": "...", "client": client, ...}}

# ==============================
# Bot Client
# ==============================

bot = TelegramClient("bot_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# ==============================
# Helper Functions
# ==============================

def is_valid_session_name(name):
    """Check if session name is valid"""
    if not name:
        return False
    # Allow only letters, numbers, underscore, hyphen
    return bool(re.match(r'^[\w\-]+$', name))

async def create_telegram_client(session_path, session_name):
    """Create a new Telegram client"""
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
    """Send login code and save client"""
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
    """Complete the login process"""
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
    """Save session files and send to user"""
    try:
        sessions_dir = os.path.expanduser("~/sessions")
        os.makedirs(sessions_dir, exist_ok=True)

        session_path = os.path.join(sessions_dir, session_name)
        session_file = session_path + ".session"

        # Save session
        await client.log_out()
        await client.connect()
        
        # Create string session
        string_session = StringSession.save(client.session)
        
        if not string_session:
            return False, "❌ ایجاد String Session ناموفق بود"

        # Save string session to file
        string_filename = f"{session_name}_string.txt"
        with open(string_filename, "w", encoding="utf-8") as f:
            f.write(string_session)

        # Send files to user
        await client.start(phone=user_sessions[user_id].get("phone"))
        
        # Send .session file
        if os.path.isfile(session_file):
            await client.send_file(
                "me",
                session_file,
                caption=f"📁 Telegram Session\nName: {session_name}"
            )
        
        # Send string session file
        await client.send_file(
            "me",
            string_filename,
            caption=f"🔐 Telegram String Session\nName: {session_name}"
        )

        return True, "✅ فایل‌های سشن با موفقیت به Saved Messages ارسال شدند"
    
    except Exception as e:
        return False, f"❌ خطا در ذخیره‌سازی: {str(e)}"

# ==============================
# Bot Handlers
# ==============================

@bot.on(events.NewMessage(pattern="/start"))
async def start_command(event):
    """Handle /start command"""
    user_id = event.sender_id
    
    # Clear user data
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
    
    # Set step
    user_sessions[user_id] = {"step": "waiting_name"}

@bot.on(events.NewMessage(pattern="/cancel"))
async def cancel_command(event):
    """Handle /cancel command"""
    user_id = event.sender_id
    
    if user_id in user_sessions:
        # Try to disconnect client if exists
        if "client" in user_sessions[user_id]:
            try:
                await user_sessions[user_id]["client"].disconnect()
            except:
                pass
        del user_sessions[user_id]
    
    if user_id in user_data:
        del user_data[user_id]
    
    await event.reply("✅ عملیات کنسل شد. برای شروع مجدد از /start استفاده کنید.")

@bot.on(events.NewMessage)
async def handle_messages(event):
    """Handle all other messages"""
    if event.is_private:
        user_id = event.sender_id
        text = event.raw_text.strip()
        
        # Check if user is in session creation process
        if user_id not in user_sessions:
            # If not, ask to start
            await event.reply("لطفاً ابتدا با دستور /start شروع کنید.")
            return
        
        step = user_sessions[user_id].get("step")
        
        # Handle session name
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
        
        # Handle phone number
        elif step == "waiting_phone":
            # Validate phone number (basic)
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
            
            # Create sessions directory
            sessions_dir = os.path.expanduser("~/sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            
            session_path = os.path.join(sessions_dir, session_name)
            
            # Create client
            client = await create_telegram_client(session_path, session_name)
            
            await event.reply("🔄 در حال اتصال به تلگرام...")
            
            try:
                await client.connect()
                user_sessions[user_id]["client"] = client
                
                # Send code
                success, message = await send_code_to_user(user_id, phone, client)
                await event.reply(message)
                
                if not success:
                    # If failed, reset step
                    user_sessions[user_id]["step"] = "waiting_phone"
                    
            except Exception as e:
                await event.reply(f"❌ خطا در اتصال: {str(e)}")
                user_sessions[user_id]["step"] = "waiting_phone"
        
        # Handle code
        elif step == "waiting_code":
            # Try to login with code
            result = await complete_login(user_id, code=text)
            
            if result[0] == "password_needed":
                user_sessions[user_id]["step"] = "waiting_password"
                await event.reply(result[1])
            
            elif result[0] is True:
                # Login successful
                await event.reply("✅ ورود با موفقیت انجام شد!\n🔄 در حال ایجاد سشن...")
                
                session_name = user_sessions[user_id]["session_name"]
                client = user_sessions[user_id]["client"]
                
                # Save and send session
                success, message = await save_session_and_send(user_id, client, session_name)
                await event.reply(message)
                
                # Clear session data
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
                # Code invalid, let user try again
                await event.reply(result[1])
        
        # Handle password
        elif step == "waiting_password":
            result = await complete_login(user_id, password=text)
            
            if result[0] is True:
                # Login successful
                await event.reply("✅ ورود با موفقیت انجام شد!\n🔄 در حال ایجاد سشن...")
                
                session_name = user_sessions[user_id]["session_name"]
                client = user_sessions[user_id]["client"]
                
                # Save and send session
                success, message = await save_session_and_send(user_id, client, session_name)
                await event.reply(message)
                
                # Clear session data
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
                # Password invalid, let user try again
                await event.reply(result[1])

# ==============================
# Main
# ==============================

async def main():
    print("=" * 50)
    print("       TELEGRAM SESSION MAKER BOT")
    print("=" * 50)
    print("Bot is running...")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    
    await bot.start()
    await bot.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped.")
