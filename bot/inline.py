import logging
import traceback
from aiogram import Router, types

from clip_client import CLIPClient
from storage_controller import StorageController

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
        found = StorageController.search(inline_query.from_user.id, inline_query.query)
        if len(found) <= 0:
            await inline_query.answer([], cache_time=0, is_personal=True,
                              switch_pm_text="Send some stickers!",
                              switch_pm_parameter="a")
            logger.info(f"No uploaded stickers for user {inline_query.from_user.username}")
            return
        result = [
            types.InlineQueryResultCachedSticker(
                id=str(i),
                sticker_file_id=found)
            for i in range(len(found))]
        logger.info("Successfully found stickers")
        await inline_query.answer(
            result,
            cache_time=0, is_personal=True,
            switch_pm_text=None, switch_pm_parameter=None)
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
