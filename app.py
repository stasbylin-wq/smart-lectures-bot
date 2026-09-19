
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from groq import Groq

# 🔑 ВСТАВЬ СВОИ ДАННЫЕ ВНУТРЬ КАВЫЧЕК:
TELEGRAM_TOKEN = "8825868450:AAGWSwOtKu2ZWWGpDzdVkoRNBnfMcFms0x4"
GROQ_API_KEY = "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"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

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
            
        with open(file_name, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=(file_name, audio_file.read()),
                model="whisper-large-v3",
                response_format="text"
            )
        
        bot.edit_message_text("✍️ Речь успешно переведена в текст! Нейросеть формирует емкий конспект, укладываясь в лимиты...", message.chat.id, status_msg.message_id)
        
        completion = groq_client.chat.completions.create(
            model="groq/compound",
            messages=[
                {"role": "system", "content": "Ты — профессиональный студенческий ассистент. Перед тобой расшифровка учебной лекции. Твоя задача — сделать КРАТКИЙ, ЕМКИЙ и СЖАТЫЙ конспект на русском языке. СТРОГО ЗАПРЕЩЕНО писать длинные тексты и лить воду. Твой итоговый ответ должен быть объемом НЕ БОЛЕЕ 3000 символов. Выдели тему лекции, разбей текст на короткие логические главы, главные термины выдели жирным шрифтом, а важные списки оформи короткими буллитами. Уложись в этот лимит при любых обстоятельствах!"},
                {"role": "user", "content": f"Вот текст лекции для сжатого конспекта:\n\n{transcription}"}
            ]
        )
        
        result_text = completion.choices.message.content
        
        bot.delete_message(message.chat.id, status_msg.message_id)
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
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    bot.infinity_polling()
