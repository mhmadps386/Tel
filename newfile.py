from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext
import requests

# التوكن الخاص ببوتك
BOT_TOKEN = "7041861528:AAFrczsJ7Wlqjqgd1uI9vn8Cg7UpMIW-NJc"

# دالة البدء
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        f"مرحباً {update.effective_user.first_name}!\n"
        "أرسل لي رقم الهاتف وسأقوم بمحاولة تحديثه."
    )

# دالة لإرسال الرقم إلى الموقع وتحسين الرسالة
def update_number_on_site(number):
    url = "https://api.areen.net/api/common/RefreshMobileNumber"  # رابط الـ API
    data = {"MobNumber": number}  # اسم الحقل MobNumber
    try:
        response = requests.post(url, json=data)  # إرسال الطلب
        if response.status_code == 200:
            response_data = response.json()
            # التحقق من كود الحالة StatusCode
            if response_data.get("StatusCode") == 993:
                return "⚠️ لا يمكن تحديث الرقم مرة أخرى خلال أقل من 3 ساعات. حاول لاحقًا."
            elif response_data.get("StatusCode") == 200:
                return "✅ تم تحديث الرقم بنجاح!"
            else:
                return f"🔔 رسالة الموقع: {response_data.get('Message', 'تم استلام الرد بنجاح')}"
        else:
            return f"❌ فشل التحديث: {response.status_code} - {response.text}"
    except Exception as e:
        return f"⚠️ حدث خطأ أثناء الاتصال بالموقع: {e}"

# دالة لمعالجة الرسائل النصية
async def handle_message(update: Update, context: CallbackContext):
    number = update.message.text.strip()  # الرقم المدخل من المستخدم
    response_message = update_number_on_site(number)  # استدعاء دالة التحديث
    await update.message.reply_text(response_message)  # إرسال الرد للمستخدم

# تشغيل البوت
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # إعداد الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("البوت يعمل الآن...")
    app.run_polling()