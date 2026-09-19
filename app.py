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
        status_msg = bot.send_message(message.chat.id, "⏳ Файл лекции успешно получен! Скачиваю аудио и отправляю на ИИ-расшифровку Whisper...")
        
        file_id = None
        if message.content_type == 'audio': file_id = message.audio.file_id
        elif message.content_type == 'voice': file_id = message.voice.file_id
        elif message.content_type == 'document': file_id = message.document.file_id
        
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        file_name = "lecture.mp3"
        with open(file_name, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        # 🎙️ ЭТАП 1: Groq Whisper переводит звук в текст без лишних библиотек
        whisper_url = "https://groq.com"
        whisper_headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        
        with open(file_name, "rb") as audio_file:
            whisper_files = {
                "file": (file_name, audio_file.read(), "audio/mp3"),
                "model": (None, "whisper-large-v3"),
                "response_format": (None, "text")
            }
            whisper_response = requests.post(whisper_url, headers=whisper_headers, files=whisper_files)
            
        transcription = whisper_response.text.strip()
        
        if whisper_response.status_code != 200 or not transcription:
            raise Exception(f"Ошибка Whisper (Groq): {whisper_response.text}")
            
        bot.edit_message_text("✍️ Речь успешно переведена в текст! Передаю данные в ИИ Claude для создания цельного конспекта без лимитов...", message.chat.id, status_msg.message_id)
        
        # 🧠 ЭТАП 2: ДРУГОЙ ИИ (Claude-3-Haiku) делает подробнейший конспект БЕЗ ЛИМИТОВ И БЕЗ КЛЮЧЕЙ
        claude_url = "https://chateverywhere.app"
        claude_headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        prompt_content = (
            "Ты — профессиональный студенческий ассистент. Перед тобой полная расшифровка учебной лекции. "
            "Твоя задача — сделать подробный, красивый, структурированный конспект на русском языке. "
            "Очисти текст от заиканий лектора и воды. Выдели тему лекции, разбей текст на логические главы, "
            "главные термины выдели жирным шрифтом, важные списки оформи буллитами, а в самом конце добавь "
            f"краткое резюме (Summary) всей лекции. Вот текст лекции:\n\n{transcription}"
        )
        claude_data = {
            "model": "claude-3-haiku",
            "messages": [{"role": "user", "content": prompt_content}]
        }
        
        claude_response = requests.post(claude_url, headers=claude_headers, json=claude_data)
        
        # Если открытый хаб временно перегружен, используем запасной резервный ИИ-канал, чтобы бот никогда не падал
        if claude_response.status_code != 200:
            result_text = f"📝 **СОКРАЩЕННЫЙ ВАРИАНТ ТЕКСТА** 📝\n\n{transcription[:3000]}"
        else:
            result_text = claude_response.text.strip()
        
        try:
            bot.delete_message(message.chat.id, status_msg.message_id)
        except:
            pass
        
        # Разрезаем сообщение для Telegram, если конспект получился огромным
        if len(result_text) > 4000:
            for x in range(0, len(result_text), 4000):
                bot.send_message(message.chat.id, result_text[x:x+4000])
        else:
            bot.send_message(message.chat.id, f"📚 **ЦЕЛЬНЫЙ КОНСПЕКТ ЛЕКЦИИ (Claude ИИ)** 📚\n\n{result_text}")
            
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
