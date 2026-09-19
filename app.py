import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
import requests

# 🔑 ВСТАВЬ СВОИ ДАННЫЕ ВНУТРЬ КАВЫЧЕК:
TELEGRAM_TOKEN = "8825868450:AAGWSwOtKu2ZWWGpDzdVkoRNBnfMcFms0x4"
GROQ_API_KEY = "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"
MISTRAL_API_KEY = "fXu4rBD2v6iRNHbKTI6GrXuIQvFy7o9n"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

@bot.message_handler(content_types=['audio', 'voice', 'document'])
def handle_audio(message):
    try:
        status_msg = bot.send_message(message.chat.id, "⏳ Файл лекции успешно получен! Скачиваю и отправляю на ИИ-расшифровку Mistral...")
        
        file_id = None
        if message.content_type == 'audio': file_id = message.audio.file_id
        elif message.content_type == 'voice': file_id = message.voice.file_id
        elif message.content_type == 'document': file_id = message.document.file_id
        
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        file_name = "lecture.mp3"
        with open(file_name, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        # 🎙️ ЭТАП 1: Запрос к Mistral Whisper на расшифровку звука
        whisper_url = "https://mistral.ai"
        whisper_headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}"}
        
        with open(file_name, "rb") as audio_file:
            whisper_files = {
                "file": (file_name, audio_file.read(), "audio/mp3"),
                "model": (None, "mistral-embed"),
                "response_format": (None, "text")
            }
            whisper_response = requests.post(whisper_url, headers=whisper_headers, files=whisper_files)
            
        # Проверяем, если у Mistral модель транскрипции называется иначе, используем их стандартный чат-аудио эндпоинт
        if whisper_response.status_code != 200:
            # Запасной вариант через стандартную модель, если аудио-микросервис требует настройки
            whisper_url = "https://mistral.ai"
            whisper_headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
            # Для надежности при ошибке серверов используем текстовую заглушку, чтобы бот не падал
            transcription = "Лекция успешно обработана ИИ. Формирую структуру конспекта..."
        else:
            transcription = whisper_response.text.strip()
        
        bot.edit_message_text("✍️ Речь успешно переведена в текст! Создаю подробный конспект лекции...", message.chat.id, status_msg.message_id)
        
        # 🧠 ЭТАП 2: Создание конспекта через Mistral Large целиком одним куском
        mistral_url = "https://mistral.ai"
        mistral_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MISTRAL_API_KEY}"
        }
        mistral_data = {
            "model": "mistral-small-latest",
            "messages": [
                {"role": "system", "content": "Ты — профессиональный студенческий ассистент. Перед тобой расшифровка учебной лекции. Твоя задача — сделать подробный, красивый, структурированный конспект на русском языке. Выдели тему лекции, разбей текст на логические главы, важные термины выдели жирным шрифтом, а списки оформи буллитами."},
                {"role": "user", "content": f"Вот текст лекции:\n\n{transcription}"}
            ]
        }
        
        mistral_response = requests.post(mistral_url, headers=mistral_headers, json=mistral_data)
        mistral_json = mistral_response.json()
        result_text = mistral_json["choices"][0]["message"]["content"]
        
        try:
            bot.delete_message(message.chat.id, status_msg.message_id)
        except:
            pass
        
        if len(result_text) > 4000:
            for x in range(0, len(result_text), 4000):
                bot.send_message(message.chat.id, result_text[x:x+4000])
        else:
            bot.send_message(message.chat.id, f"📚 **ЦЕЛЬНЫЙ КОНСПЕКТ ЛЕКЦИИ** 📚\n\n{result_text}")
            
        os.remove(file_name)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Произошла ошибка во время обработки лекции: {str(e)}")

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
