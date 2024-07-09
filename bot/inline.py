from os import getenv
import logging

from aiogram import Router, types
from qdrant_client.async_qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

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
    try:
        # check if user does not have any uploaded stickers
        qdrant = AsyncQdrantClient(url=QDRANT, api_key=QDRANT_API_KEY)
        uploaded = await qdrant.count(
            collection_name=COLLECTION,
            count_filter=Filter(
                must=[
                    FieldCondition(
                        key='chat_id',
                        match=MatchValue(value=inline_query.from_user.id)
                    )
                ]
            )
        )
        if uploaded.count >= 1:
            await inline_query.answer([], cache_time=0, is_personal=True,
                              switch_pm_text="Send some stickers!",
                              switch_pm_parameter="a")
            logger.debug(f"No uploaded stickers for user {inline_query.from_user.username}")
            return
    except:
        logger.error("Error occured, I hope some one wrote more about it")
    finally:
        await qdrant.close()
