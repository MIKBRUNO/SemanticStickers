import telebot
import requests
from io import BytesIO
import uuid
import os

bot = telebot.TeleBot(os.getenv('TELEGRAM_BOT_TOKEN'))


@bot.message_handler(content_types=['sticker'])
def handle_sticker(message):
    sticker: telebot.types.Sticker = message.sticker
    if sticker.is_video or sticker.is_animated:
        bot.send_message(message.chat.id, 'Not supported sticker')
        return
    file = bot.get_file(sticker.file_id)
    file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
    response = requests.get(file_url)
    if response.status_code != 200:
        bot.send_message(message.chat.id, "Couldn't load a sticker")
        return
    response = requests.post(os.getenv('CLIP_URL') + "/upload_image", files={'image': BytesIO(response.content)})
    if response.status_code != 200:
        bot.send_message(message.chat.id, "Couldn't vectorize sticker")
        return

    """
    Checking the repetition of the sticker. 
    Upload sticker to Qdrant.
    """
    

@bot.message_handler(content_types=['text'])
def handle_sticker_id(message):
    url = os.getenv('CLIP_URL') + '/process_text'
    response = requests.post(url, json={'text': message.text})
    if response.status_code != 200:
        bot.send_message(message.chat.id, "Couldn't find sticker")
        return
    """
    Search for a sticker and send it
    """


bot.polling()
