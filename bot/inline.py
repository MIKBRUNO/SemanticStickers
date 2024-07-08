from os import getenv
import logging

from aiogram import Router, types

QDRANT = getenv('QDRANT_URL')
QDRANT_API_KEY = getenv('QDRANT_API_KEY')
CLIP = getenv('CLIP_URL')

logger = logging.getLogger(__name__)
inline_router = Router(name="inline")

@inline_router.inline_query()
async def inline_query_handler(inline_query: types.InlineQuery) -> None:
    await inline_query.answer([], cache_time=0, is_personal=True,
                              switch_pm_text="Send some stickers!",
                              switch_pm_parameter="a")

