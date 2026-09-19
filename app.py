import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from groq import Groq

# 🔑 ВСТАВЬ СВОИ ДАННЫЕ ВНУТРЬ КАВЫЧЕК:
TELEGRAM_TOKEN = "8825868450:AAGWSwOtKu2ZWWGpDzdVkoRNBnfMcFms0x4"
GROQ_API_KEY = "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"
MISTRAL_API_KEY = "fXu4rBD2v6iRNHbKTI6GrXuIQvFy7o9n"


bot = telebot.TeleBot(TELEGRAM_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

def split_text_by_words(text, max_chars=4000):
    """Функция нарезки текста лекции на безопасные куски для обхода лимитов Groq"""
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
        status_msg = bot.reply_to(message, "⏳ Файл лекции успешно получен! Скачиваю аудио и отправляю ИИ Whisper на расшифровку...")
        
        file_id = None
        if message.content_type == 'audio': file_id = message.audio.file_id
        elif message.content_type == 'voice': file_id = message.voice.file_id
        elif message.content_type == 'document': file_id = message.document.file_id
        
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        file_name = "lecture.mp3"
        with open(file_name, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        # 1. Whisper переводит ВСЕ 1.5 ЧАСА в текст целиком
        with open(file_name, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=(file_name, audio_file.read()),
                model="whisper-large-v3",
                response_format="text"
            )
        
        bot.edit_message_text("✍️ Речь успешно переведена в текст! Обхожу минутные лимиты и формирую конспект...", message.chat.id, status_msg.message_id)
        
        # 2. Вместо обрезки — режем текст на куски по 4000 символов в памяти
        text_chunks = split_text_by_words(transcription, max_chars=4000)
        final_notes = []
        
        for i, chunk in enumerate(text_chunks):
            # Отправляем кусочки лекции по очереди в стабильную модель groq/compound
            completion = groq_client.chat.completions.create(
                model="groq/compound",
                messages=[
                    {"role": "system", "content": "Ты — профессиональный студенческий ассистент. Перед тобой фрагмент расшифровки учебной лекции. Твоя задача — сделать КРАТКИЙ, ЕМКИЙ и СЖАТЫЙ конспект этой части на русском языке. Убирай воду, повторы и слова-паразиты лектора. Главные термины выдели жирным шрифтом, а важные тезисы оформи короткими буллитами."},
                    {"role": "user", "content": f"Сделай конспект фрагмента №{i+1}:\n\n{chunk}"}
                ]
            )
            final_notes.append(completion.choices[0].message.content)
            # Пауза 4 секунды между кусками, чтобы бесплатный лимит (TPM) гарантированно успевал обнуляться
            if i < len(text_chunks) - 1:
                time.sleep(60)
        
        # Склеиваем все части в один монолитный конспект лекции
        result_text = f"📚 **ИДЕАЛЬНЫЙ ЦЕЛЬНЫЙ КОНСПЕКТ ЛЕКЦИИ** 📚\n\n" + "\n\n".join(final_notes)
        
        try:
            bot.delete_message(message.chat.id, status_msg.message_id)
        except:
            pass
            
        # Защита от лимита самого Telegram на длину одного сообщения
        if len(result_text) > 4000:
            for x in range(0, len(result_text), 4000):
                bot.send_message(message.chat.id, result_text[x:x+4000], parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, result_text, parse_mode="Markdown")
            
        os.remove(file_name)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Произошла ошибка во время обработки лекции: {str(e)}")

# Заглушка веб-сервера для бесплатного тарифа Render
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
    # 💥 ЖЕЛЕЗОБЕТОННЫЙ СБРОС: Принудительно очищаем зависшие вебхуки Telegram при старте
    try:
        bot.remove_webhook()
    except:
        pass
        
    threading.Thread(target=run_web_server, daemon=True).start()
    bot.infinity_polling()
    threading.Thread(target=run_web_server, daemon=True).start()
    bot.infinity_polling()
