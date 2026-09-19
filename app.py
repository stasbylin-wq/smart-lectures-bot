import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from groq import Groq
import google.generativeai as genai

# 🔑 ВСТАВЬ СВОИ ДАННЫЕ ВНУТРЬ КАВЫЧЕК:
TELEGRAM_TOKEN = "8825868450:AAGWSwOtKu2ZWWGpDzdVkoRNBnfMcFms0x4"
GROQ_API_KEY = "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"
GEMINI_API_KEY = "AQ.Ab8RN6LTHndhLop7DD2SFCl294X-g9BU5lVIKwddOcCtiF5-uw"
bot = telebot.TeleBot(TELEGRAM_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

# Классическая и стабильная конфигурация Google ИИ
genai.configure(api_key=GEMINI_API_KEY)

@bot.message_handler(content_types=['audio', 'voice', 'document'])
def handle_audio(message):
    try:
        status_msg = bot.send_message(message.chat.id, "⏳ Аудио лекции успешно получено! Скачиваю и отправляю ИИ Whisper на расшифровку...")
        
        file_id = None
        if message.content_type == 'audio': file_id = message.audio.file_id
        elif message.content_type == 'voice': file_id = message.voice.file_id
        elif message.content_type == 'document': file_id = message.document.file_id
        
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        file_name = "lecture.mp3"
        with open(file_name, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        # 🎙️ ЭТАП 1: Groq делает бесплатный перевод звука в текст
        with open(file_name, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=(file_name, audio_file.read()),
                model="whisper-large-v3",
                response_format="text"
            )
        
        bot.edit_message_text("✍️ Текст успешно распознан! Передаю данные в Google Gemini для создания гигантского конспекта без лимитов...", message.chat.id, status_msg.message_id)
        
        # 🧠 ЭТАП 2: Супер-стабильная модель Gemini 1.5 Flash делает конспект без лимитов
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(
            f"Ты — professional студенческий ассистент. Перед тобой полная расшифровка учебной лекции. Твоя задача — сделать подробный, красивый, структурированный конспект на русском языке. Очисти текст от заиканий лектора и воды. Выдели тему лекции, разбей текст на логические главы, важные термины выдели жирным шрифтом, важные списки оформи буллитами, а в самом конце добавь краткое резюме (Summary) всей лекции. Вот текст лекции:\n\n{transcription}"
        )
        
        result_text = response.text
        
        try:
            bot.delete_message(message.chat.id, status_msg.message_id)
        except:
            pass
        
        # Разрезаем сообщение для Telegram, если конспект получился очень большим (лимит TG 4096 символов)
        if len(result_text) > 4000:
            for x in range(0, len(result_text), 4000):
                bot.send_message(message.chat.id, result_text[x:x+4000])
        else:
            bot.send_message(message.chat.id, f"📚 КОНСПЕКТ ЛЕКЦИИ 📚\n\n{result_text}")
            
        os.remove(file_name)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Произошла ошибка во время обработки лекции: {str(e)}")

# Сервер для удержания Render тарифа Free
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_web_server():
    server = HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), HealthCheckHandler)
    server.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    bot.infinity_polling()
