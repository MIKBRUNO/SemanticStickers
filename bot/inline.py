from os import getenv
import logging
import traceback

from aiogram import Router, types
from aiohttp import ClientSession
from qdrant_client.async_qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from clip_client import CLIPClient

REDIS = getenv('REDIS_URL')
QDRANT = getenv('QDRANT_URL')
QDRANT_API_KEY = getenv('QDRANT_API_KEY')
CLIP = getenv('CLIP_URL')
COLLECTION = getenv('QDRANT_COLLECTION')

logger = logging.getLogger(__name__)
inline_router = Router(name="inline")

@inline_router.inline_query()
async def inline_query_handler(inline_query: types.InlineQuery) -> None:
    """Handler for inline queries

    This handlers accepts all the inline queries by users, encodes it via
    CLIP server and searches for nearest saved stickers
    """
    logger.info(f"Inline query from {inline_query.from_user.username}: {inline_query.query}")
    qdrant = AsyncQdrantClient(url=QDRANT, api_key=QDRANT_API_KEY)
    try:        
        # encode inline query
        vector = await CLIPClient(REDIS).process_text(
            str(inline_query.from_user.id), inline_query.query,
            timeout=60
        )
        logger.debug(f"Embedding: {vector}")

        # search for nearest 50 stickers
        found = await qdrant.search(
            collection_name=COLLECTION,
            query_vector=vector,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key='users',
                        match=MatchValue(value=inline_query.from_user.id)
                    )
                ]
            ),
            limit=50,
            with_payload=True,
            with_vectors=False
        )
        logger.debug(f"Found {len(found)} stickers")
        if len(found) <= 0:
            await inline_query.answer([], cache_time=0, is_personal=True,
                              switch_pm_text="Send some stickers!",
                              switch_pm_parameter="a")
            logger.info(f"No uploaded stickers for user {inline_query.from_user.username}")
            return
        result = [
            types.InlineQueryResultCachedSticker(
                id=str(i),
                sticker_file_id=found[i].payload['file_id'])
            for i in range(len(found))]
        logger.info("Successfully found stickers")
        await inline_query.answer(result, cache_time=0, is_personal=True, switch_pm_text=None, switch_pm_parameter=None)
    except TimeoutError as e:
        await inline_query.answer([], cache_time=0, is_personal=True,
                              switch_pm_text="Oops...",
                              switch_pm_parameter="o")
        logger.warn("Text request timeout")
    except Exception as e:
        await inline_query.answer([], cache_time=0, is_personal=True,
                              switch_pm_text="Oops...",
                              switch_pm_parameter="o")
        logger.error(traceback.format_exc())
    finally:
        await qdrant.close()
