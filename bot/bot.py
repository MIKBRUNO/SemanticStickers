import telebot
import requests
from io import BytesIO
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
import uuid
import os

bot = telebot.TeleBot(os.getenv('TELEGRAM_BOT_TOKEN'))
qdrant_url = os.getenv('QDRANT_URL')
qdrant_api_key = os.getenv('QDRANT_API_KEY')
clip_url = os.getenv('CLIP_URL')

@bot.message_handler(commands=['donate'])
def send_crypto_address(message):
    wallet_address = "UQCWjkiD4mYn-vkl53WVrttQ9AAFLpoSgh1OLXIyjsmRhsSj"
    bot.send_message(message.chat.id, f"You're on right way, now to make telegram a better place, just send donation to this TON address: {wallet_address} Humanity will be proud of you!")


@bot.message_handler(content_types=['sticker'])
def handle_sticker(message):
    sticker: telebot.types.Sticker = message.sticker
    if sticker.is_video or sticker.is_animated:
        bot.send_message(message.chat.id, 'Animated stickers are not supported yet (')
        return
    file = bot.get_file(sticker.file_id)
    file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
    response = requests.get(file_url)
    if response.status_code != 200:
        bot.send_message(message.chat.id, "Couldn't load a sticker")
        return
    response = requests.post(clip_url + "/upload_image", files={'image': BytesIO(response.content)})
    if response.status_code != 200:
        bot.send_message(message.chat.id, "Couldn't vectorize sticker")
        return
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
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
    client.close()


@bot.message_handler(content_types=['text'])
def handle_search_query(message):
    if message.text.startswith('/'):
        #skip commands
        return
    url = clip_url + '/process_text'
    response = requests.post(url, json={'text': message.text})
    if response.status_code != 200:
        bot.send_message(message.chat.id, "Couldn't find sticker")
        return
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
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
    client.close()


@bot.inline_handler(func=lambda query: True)
def handle_inline_query(inline_query: telebot.types.InlineQuery):
    url = clip_url + '/process_text'
    response = requests.post(url, json={'text': inline_query.query})
    if response.status_code != 200:
        r = telebot.types.InlineQueryResultArticle(
            '1',
            'Sorry!',
            telebot.types.InputTextMessageContent('Some eternal error occurred')
        )
        bot.answer_inline_query(inline_query.id, [r])
        return
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    result = client.search(
        collection_name='SemanticStickers',
        query_vector=response.json()['embed'],
        query_filter=Filter(
            must=[
                FieldCondition(
                    key='chat_id',
                    match=MatchValue(value=inline_query.from_user.id)
                )
            ]
        ),
        limit=30,
        with_payload=True,
        with_vectors=False
    )
    if len(result) == 0:
        r = telebot.types.InlineQueryResultArticle(
            '1',
            'It seems like you didn\'t load any stickers yet',
            telebot.types.InputTextMessageContent('@SemanticStickersBot')
        )
        bot.answer_inline_query(inline_query.id, [r])
        return
    client.close()
    stickers = []
    for i in range(len(result)):
        stickers.append(telebot.types.InlineQueryResultCachedSticker(
            str(i),
            result[i].payload['file_id']
        ))
    bot.answer_inline_query(inline_query.id, stickers, cache_time=1, is_personal=True)



bot.infinity_polling()
