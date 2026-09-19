
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from groq import Groq

# 🔑 ВСТАВЬ СВОИ ДАННЫЕ ВНУТРЬ КАВЫЧЕК:
TELEGRAM_TOKEN = "8825868450:AAGWSwOtKu2ZWWGpDzdVkoRNBnfMcFms0x4"
GROQ_API_KEY = "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"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

def split_text(text, max_chars=3000):
    """Функция автоматической нарезки текста для обхода секундных и минутных лимитов Groq"""
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0
    for word in words:
        if current_length + len(word) + 1 > max_chars:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_length = len(word)
        else:
            current_chunk.append(word)
            current_length += len(word) + 1
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

@bot.message_handler(content_types=['audio', 'voice', 'document'])
def handle_audio(message):
    try:
        status_msg = bot.reply_to(message, "⏳ Файл лекции успешно получен! Скачиваю аудио и отправляю ИИ Whisper на расшифровку... Пожалуйста, подождите около минуты.")
        
        file_id = None
        if message.content_type == 'audio': file_id = message.audio.file_id
        elif message.content_type == 'voice': file_id = message.voice.file_id
        elif message.content_type == 'document': file_id = message.document.file_id
        
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        file_name = "lecture.mp3"
        with open(file_name, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        # ТУТ СТРОГО СЛУШАЕТ WHISPER
        with open(file_name, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=(file_name, audio_file.read()),
                model="whisper-large-v3",
                response_format="text"
            )
        
        bot.edit_message_text("✍️ Речь успешно переведена в текст! Обхожу лимиты Groq и формирую конспект...", message.chat.id, status_msg.message_id)
        
        # Режем огромную лекцию на безопасные части по 3000 символов
        text_chunks = split_text(transcription, max_chars=3000)
        final_notes = []
        
        for i, chunk in enumerate(text_chunks):
            # ТУТ СТРОГО КОНСПЕКТИРУЕТ COMPOUND КУСОЧКАМИ
            completion = groq_client.chat.completions.create(
                model="groq/compound",
                messages=[
                    {"role": "system", "content": "Ты — профессиональный студенческий ассистент. Перед тобой кусок расшифровки учебной лекции. Твоя задача — сделать КРАТКИЙ, ЕМКИЙ и СЖАТЫЙ конспект этой части на русском языке. Убирай заикания лектора и воду. Главные термины выдели жирным шрифтом, а важные списки оформи короткими буллитами."},
                    {"role": "user", "content": f"Сделай конспект для части {i+1}:\n\n{chunk}"}
                ]
            )
            final_notes.append(completion.choices.message.content)
            # Пауза 4 секунды между запросами, чтобы обнулился минутный лимит (TPM)
            time.sleep(4)
            
        # Соединяем конспект воедино
        result_text = f"📚 **ИДЕАЛЬНЫЙ КОНСПЕКТ ЛЕКЦИИ** 📚\n\n" + "\n\n".join(final_notes)
        
        bot.delete_message(message.chat.id, status_msg.message_id)
        
        # Защита от лимита длины сообщения самого Telegram
        if len(result_text) > 4000:
            for x in range(0, len(result_text), 4000):
                bot.send_message(message.chat.id, result_text[x:x+4000], parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, result_text, parse_mode="Markdown")
            
        os.remove(file_name)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Произошла ошибка во время обработки лекции: {str(e)}")

# Служебный веб-сервер для удержания бесплатного тарифа Render
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    bot.infinity_polling()
