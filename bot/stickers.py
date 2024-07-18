from os import getenv
import logging
import traceback
import uuid

from aiohttp import ClientSession
from aiogram import Router, types, F, Bot
from aiogram.filters import MagicData

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, PointStruct

from clip_client import CLIPClient

QDRANT = getenv('QDRANT_URL')
QDRANT_API_KEY = getenv('QDRANT_API_KEY')
CLIP = getenv('CLIP_URL')
COLLECTION = getenv('QDRANT_COLLECTION')
REDIS = getenv('REDIS_URL')

logger = logging.getLogger(__name__)
stickers_router = Router(name="stickers")

@stickers_router.message(MagicData(F.event.sticker != None))
async def sticker_handler(message: types.Message, bot: Bot) -> None:
    """Handler for incoming stickers

    This handler accepts stickers, loads source image, sends it to encoding
    CLIP server and finally saves it in Qdrant storage
    """
    sticker = message.sticker
    logger.info(f"New sticker request from user {message.from_user.username}"
                f", unique_id: {sticker.file_unique_id}, id: {sticker.file_id}")
    
    qdrant = AsyncQdrantClient(url=QDRANT, api_key=QDRANT_API_KEY)
    try:
        # check if this sticker is already in storage
        retrived = await qdrant.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="unique_id", match=MatchValue(value=sticker.file_unique_id)),
                ]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        retrived = retrived[0]
        if len(retrived) > 0:
            sticker_record = retrived[0]
            # answer if user sent a duplicate
            if message.from_user.id in sticker_record.payload['users']:
                await message.answer('Duplicate')
                logger.info(f"Got a duplicate")
                return
            await qdrant.set_payload(
                collection_name=COLLECTION,
                payload={"users": sticker_record.payload['users'] + [message.from_user.id]},
                points=[sticker_record.id]
            )
            logger.info("Added new user to sticker record "
                    f"unique_id: {sticker.file_unique_id}, id: {sticker.file_id}"
                    f"from user {message.from_user.username}")
            await message.answer('Uploaded!')
            return
        
        # download and embed
        file = await bot.get_file(message.sticker.file_id)
        if sticker.is_video or sticker.is_animated:
            file = await bot.get_file(message.sticker.thumbnail.file_id)
        url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        vector = await CLIPClient(REDIS).process_image(url)
        logger.debug(f"Embedding: {vector}")
        
        # save to qdrant storage
        await qdrant.upload_points(
            collection_name=COLLECTION,
            wait=True,
            points=[
                PointStruct(
                    id=str(uuid.uuid1()),
                    vector=vector,
                    payload={
                        'users': [message.from_user.id],
                        "unique_id": sticker.file_unique_id,
                        "file_id": sticker.file_id,
                        "type": sticker.type,
                        "is_video": sticker.is_video,
                        "is_animated": sticker.is_animated,
                        "set_name": sticker.set_name,
                        "emoji": sticker.emoji
                    })
            ]
        )
        logger.info("Uploaded new sticker "
                    f"unique_id: {sticker.file_unique_id}, id: {sticker.file_id}"
                    f"from user {message.from_user.username}")
        await message.answer('Uploaded!')
    except:
        logger.error(traceback.format_exc())
        await message.answer('Could not upload your sticker( Try next time!')
    finally:
        await qdrant.close()
