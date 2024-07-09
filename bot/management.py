"""All management handlers for telegram bot

Here we place all handlers that do not directly relate to main logic
"""

import logging
from aiogram import Router
from aiogram import types
from aiogram.filters.command import Command

logger = logging.getLogger(__name__)
management_router = Router(name="management")

@management_router.message(Command("donate"))
async def donate_command_handler(message: types.Message) -> None:
    """A handler for command /donate

    Just a simple command handler that sends message with crypto wallet
    """
    wallet_address = "UQCWjkiD4mYn-vkl53WVrttQ9AAFLpoSgh1OLXIyjsmRhsSj"
    await message.answer(
            "You're on right way, now to make telegram a better place,"
            "just send donation to this TON address:"
            f"\n{wallet_address}" 
            "\nHumanity will be proud of you!")
    logger.info(f"User {message.from_user.username} wanted to donate!!!")
    
