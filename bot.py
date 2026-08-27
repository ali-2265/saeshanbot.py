import os
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import Message

API_ID = YOUR_API_ID  # عدد API ID خود را وارد کنید
API_HASH = "YOUR_API_HASH"  # API Hash خود را وارد کنید
BOT_TOKEN = "YOUR_BOT_TOKEN"  # توکن ربات خود را اینجا وارد کنید

# دیکشنری برای ذخیره وضعیت کاربران
user_sessions = {}

class SessionBot:
    def __init__(self):
        # ایجاد کلاینت با توکن ربات
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
        self.temp_clients = {}  # ذخیره کلاینت‌های موقت برای هر کاربر

    async def start(self):
        # شروع ربات با توکن
        await self.bot.start(bot_token=BOT_TOKEN)
        print("ربات راه‌اندازی شد!")

        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start_command(event):
            user_id = event.sender_id
            
            # ایجاد کلاینت موقت برای این کاربر
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
                'step': 'phone'  # مرحله فعلی
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
                        
                        # اتصال به تلگرام
                        await client.connect()
                        
                        if not await client.is_user_authorized():
                            try:
                                # ارسال درخواست کد
                                await client.send_code_request(phone)
                                user_data['phone'] = phone
                                user_data['step'] = 'code'
                                
                                await event.respond(
                                    "✅ کد تأیید به شماره شما ارسال شد.\n\n"
                                    "📝 لطفاً کد ۵ رقمی دریافت شده را وارد کنید:"
                                )
                            except Exception as e:
                                await event.respond(f"❌ خطا: {str(e)}")
                        else:
                            await event.respond("⚠️ این شماره قبلاً تأیید شده است!")
                    
                    elif step == 'code':
                        code = event.text.strip()
                        phone = user_data.get('phone')
                        
                        if not phone:
                            await event.respond("❌ شماره تلفن یافت نشد. دوباره /start را بزنید.")
                            return
                        
                        try:
                            # ورود با کد
                            await client.sign_in(phone, code)
                            
                            # ذخیره سشن
                            session_file = user_data['session_path'] + ".session"
                            
                            if os.path.isfile(session_file):
                                # ارسال فایل سشن به کاربر
                                await client.send_file(
                                    "me",
                                    session_file,
                                    caption=f"📁 فایل سشن: {user_data['session_name']}"
                                )
                                
                                # ارسال فایل به ربات برای کاربر
                                await event.respond(
                                    "✅ ورود موفقیت‌آمیز بود!\n\n"
                                    "📁 فایل سشن شما به Saved Messages ارسال شد.\n"
                                    "🔗 همچنین می‌توانید فایل را از اینجا دانلود کنید:"
                                )
                                
                                # ارسال فایل به کاربر در ربات
                                await self.bot.send_file(
                                    event.chat_id,
                                    session_file,
                                    caption=f"📁 فایل سشن: {user_data['session_name']}"
                                )
                                
                                # پاک کردن داده‌های موقت
                                del self.temp_clients[user_id]
                            else:
                                await event.respond("❌ خطا: فایل سشن ایجاد نشد!")
                                
                        except Exception as e:
                            error_msg = str(e)
                            if "PHONE_CODE_INVALID" in error_msg:
                                await event.respond("❌ کد وارد شده اشتباه است. دوباره تلاش کنید:")
                            elif "CODE_EXPIRED" in error_msg:
                                await event.respond("❌ کد منقضی شده است. دوباره /start را بزنید.")
                            elif "PHONE_NUMBER_UNOCCUPIED" in error_msg:
                                await event.respond("❌ شماره تلفن معتبر نیست!")
                            else:
                                await event.respond(f"❌ خطا: {error_msg}")
                                # اگر خطا جدی بود، داده‌ها را پاک کن
                                if "FLOOD" not in error_msg:
                                    del self.temp_clients[user_id]
                
                except Exception as e:
                    await event.respond(f"❌ خطای غیرمنتظره: {str(e)}")
                    # پاک کردن داده‌های مشکل‌دار
                    if user_id in self.temp_clients:
                        del self.temp_clients[user_id]

        # نمایش اطلاعات ربات
        me = await self.bot.get_me()
        print(f"🤖 ربات با نام @{me.username} آماده است!")
        print(f"📱 برای شروع، ربات را با /start استارت کنید.")

        await self.bot.run_until_disconnected()

async def main():
    bot = SessionBot()
    await bot.start()

if __name__ == "__main__":
    # ایجاد پوشه سشن‌ها
    os.makedirs(os.path.expanduser("~/sessions"), exist_ok=True)
    
    # اجرای ربات
    asyncio.run(main())
