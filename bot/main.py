import asyncio
import logging
import sys
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

TOKEN = getenv('TELEGRAM_BOT_TOKEN')
logger = logging.getLogger(__name__)

# some logic is separated beetween few routers, here they get connected
dp = Dispatcher()
import stickers
import inline
dp.include_router(stickers.stickers_router)
dp.include_router(inline.inline_router)


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    asyncio.run(main())
