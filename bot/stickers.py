import logging
import traceback

from aiogram import Router, types, F, Bot
from aiogram.filters import MagicData

from storage_controller import StorageController

logger = logging.getLogger(__name__)
stickers_router = Router(name="stickers")


async def get_sticker_file_url(bot, sticker) -> str:
    file = await bot.get_file(sticker.file_id)
    if sticker.is_video or sticker.is_animated:
        file = await bot.get_file(sticker.thumbnail.file_id)
    return f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"


@stickers_router.message(MagicData(F.event.sticker != None))
async def sticker_handler(message: types.Message, bot: Bot) -> None:
    """Handler for incoming stickers

    This handler accepts stickers, loads source image, sends it to encoding
    CLIP server and finally saves it in Qdrant storage
    """
    sticker = message.sticker
    logger.info(f"New sticker request from user {message.from_user.username}"
                f", unique_id: {sticker.file_unique_id}, id: {sticker.file_id}")
    if sticker.set_name is None:
        logger.info(f"Sticker is orphan, so poor(...")
        await message.reply('This sticker is not in any sticker set. '
                            'Now we do not support such stickers')
        return

    try:
        res = await StorageController.upload(
            message.from_user.id,
            sticker.file_unique_id,
            sticker.file_id,
            sticker.type,
            sticker.is_video,
            sticker.is_animated,
            sticker.set_name,
            sticker.emoji,
            get_sticker_file_url(bot, sticker)
        )

        if res == StorageController.UploadStatus.DUPLICATE:
            await message.reply('Duplicate')
            logger.info(f"Got a duplicate")
            return
        elif res == StorageController.UploadStatus.UPDATED:
            logger.info("Added new user to sticker record "
                    f"unique_id: {sticker.file_unique_id}, id: {sticker.file_id}"
                    f"from user {message.from_user.username}")
            await message.reply('Uploaded!')
            return
        elif res == StorageController.UploadStatus.UPLOADED:
            logger.info("Uploaded new sticker "
                        f"unique_id: {sticker.file_unique_id}, id: {sticker.file_id}"
                        f"from user {message.from_user.username}")
            await message.reply('Uploaded!')
            return
        elif res == StorageController.UploadStatus.FAILURE:
            await message.reply('Could not upload your sticker( Try next time!')
            return
    
    except:
        logger.error(traceback.format_exc())
        await message.reply('Could not upload your sticker( Try next time!')
