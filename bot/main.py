import asyncio
import logging
import sys
from os import getenv

from aiogram import Bot, Dispatcher, html, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

# for nice colored logs
import coloredlogs
coloredlogs.install()


TOKEN = getenv('TELEGRAM_BOT_TOKEN')
logger = logging.getLogger(__name__)

# some logic is segregated beetween few routers, here they get connected
dp = Dispatcher()
import management
import stickers
import inline
dp.include_router(management.management_router)
dp.include_router(stickers.stickers_router)
dp.include_router(inline.inline_router)


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.BASIC_FORMAT
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
