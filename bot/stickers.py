from os import getenv
import logging
import uuid

from aiohttp import ClientSession
from aiogram import Router, types, F, Bot
from aiogram.filters import MagicData

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, PointStruct

QDRANT = getenv('QDRANT_URL')
QDRANT_API_KEY = getenv('QDRANT_API_KEY')
CLIP = getenv('CLIP_URL')

logger = logging.getLogger(__name__)
stickers_router = Router(name="stickers")

@stickers_router.message(MagicData(F.event.sticker != None))
async def sticker_handler(message: types.Message, bot: Bot) -> None:
    sticker = message.sticker
    logger.info(f"New sticker request from user {message.from_user.username}"
                f", unique_id: {sticker.file_unique_id}")
    
    try:
        qdrant = AsyncQdrantClient(url=QDRANT, api_key=QDRANT_API_KEY)
        duplicates = await qdrant.count(
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
        if duplicates.count >= 1:
            await message.answer('Duplicate')
            logger.debug(f"Got a duplicate ({duplicates.count})")
            return
        
        file = await bot.get_file(message.sticker.file_id)
        if sticker.is_video or sticker.is_animated:
            file = await bot.get_file(message.sticker.thumbnail.file_id)
        io = await bot.download(file)
        vector = []
        async with ClientSession() as session:
            async with session.post(CLIP + "/upload_image", data={"image": io}) as response:
                vector = response.json()['embed']
        
        await qdrant.upload_points(
            collection_name="SemanticStickers",
            wait=True,
            points=[
                PointStruct(
                    id=str(uuid.uuid1()),
                    vector=vector,
                    payload={
                        "file_id": sticker.file_id,
                        'chat_id': message.chat.id,
                        'unique_id': sticker.file_unique_id
                    })
            ]
        )
        await message.answer('Uploaded!')
    except:
        await message.answer('Could not upload your sticker( Try next time!')
    finally:
        await qdrant.close()
