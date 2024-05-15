import telebot
import requests
from io import BytesIO
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
import uuid
import os

bot = telebot.TeleBot(os.getenv('TELEGRAM_BOT_TOKEN'))

client = QdrantClient(url=os.getenv('QDRANT_URL'))


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
    res = client.count(
        collection_name="SemanticStickers",
        count_filter=Filter(
            must=[
                FieldCondition(
                    key='chat_id',
                    match=MatchValue(value=message.chat.id)
                ),
                FieldCondition(
                    key='unique_id',
                    match=MatchValue(value=sticker.file_unique_id)
                )
            ]
        )
    )
    if res.count > 0:
        bot.send_message(message.chat.id, 'Duplicate')
        return
    client.upload_points(
        collection_name="SemanticStickers",
        wait=True,
        points=[
            PointStruct(
                id=str(uuid.uuid1()),
                vector=response.json()['embed'],
                payload={
                    "file_id": sticker.file_id,
                    'chat_id': message.chat.id,
                    'unique_id': sticker.file_unique_id
                })
        ]
    )
    bot.send_message(message.chat.id, 'Uploaded!')
    

@bot.message_handler(content_types=['text'])
def handle_sticker_id(message):
    url = os.getenv('CLIP_URL') + '/process_text'
    response = requests.post(url, json={'text': message.text})
    if response.status_code != 200:
        bot.send_message(message.chat.id, "Couldn't find sticker")
        return
    result = client.search(
        collection_name='SemanticStickers',
        query_vector=response.json()['embed'],
        query_filter=Filter(
            must=[
                FieldCondition(
                    key='chat_id',
                    match=MatchValue(value=message.chat.id)
                )
            ]
        ),
        limit=1,
        with_payload=True,
        with_vectors=False
    )
    if len(result) == 0:
        bot.send_message(message.chat.id, "Not found")
        return
    bot.send_sticker(message.chat.id, result[0].payload['file_id'])


bot.polling()
