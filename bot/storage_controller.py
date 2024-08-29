from os import getenv
import logging
from enum import Enum
from typing import Awaitable
import uuid

from qdrant_client.async_qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, PointStruct

from clip_client import CLIPClient

REDIS = getenv('REDIS_URL')
QDRANT = getenv('QDRANT_URL')
QDRANT_API_KEY = getenv('QDRANT_API_KEY')
CLIP = getenv('CLIP_URL')
COLLECTION = getenv('QDRANT_COLLECTION')

logger = logging.getLogger(__name__)

class StorageController:
    """API for interacting with semantic storage

    Static class that implements search, upload and whatever you want
    (yes like deletion)
    """

    async def search(
            user_id: str, text: str,
            limit: int=50, timeout: float | None=60) -> list[str]:
        """Searches for stickers by text
        Attributes:
            user_id (str): user id of search request. If request was not started to proceed,
            it can be replaced with another request by same user
            text (str): text to search by
            limit (int): Optional. Maximum stickers to find
            timeout (float | None): timeout to wait after sending request
        Returns: list of strings - stickers' file_ids, may be empty
        Raises:
            CLIPServerException: see CLIPClient.process_text
            TimeoutError: raises when search request was abandoned
            by sending another search request from the same user
            мех, but works
        """
        qdrant = AsyncQdrantClient(url=QDRANT, api_key=QDRANT_API_KEY)
        try:        
            # encode inline query
            vector = await CLIPClient(REDIS).process_text(
                str(user_id), text,
                timeout=timeout
            )
            logger.debug(f"Embedding: {vector}")

            # search for nearest stickers
            found = await qdrant.search(
                collection_name=COLLECTION,
                query_vector=vector,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key='users',
                            match=MatchValue(value=user_id)
                        )
                    ]
                ),
                limit=limit,
                with_payload=True,
                with_vectors=False
            )
            logger.debug(f"Found {len(found)} stickers")
            return [record.payload['file_id'] for record in found]
        except Exception as e:
            await qdrant.close()
            raise e


    class UploadStatus(Enum):
        DUPLICATE=0
        UPLOADED=1
        UPDATED=2
        FAILURE=3


    async def upload(
            user_id: str, unique_id: str, file_id: str, type: str,
            is_video: bool, is_animated: bool, set_name: str,
            emoji: str, sticker_file_coro: Awaitable) -> UploadStatus:
        """Upload sticker
        Attributes:
            user_id (str): user id of sticker sender. Used to check duplicates
            unique_id (str): sticker file unique id
            file_id (str): sticker file id
            type (str): sticker type
            is_video (bool): sticker is_video
            is_animated (bool): sticker is_animated
            set_name (str): sticker set_name
            emoji (str): sticker emoji
            sticker_file_coro (Awaitable): coroutine to get sticker file url.
            Can be not called
        Returns: upload status: duplicate, success or failure
        Raises:
            CLIPServerException: see CLIPClient.process_text
        """
        qdrant = AsyncQdrantClient(url=QDRANT, api_key=QDRANT_API_KEY)
        try:
            # check if this sticker is already in storage
            retrived = await qdrant.scroll(
                collection_name=COLLECTION,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="unique_id", match=MatchValue(value=unique_id)),
                    ]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False,
            )
            # get rid of qdrant redudant info
            retrived = retrived[0]
            if len(retrived) > 0:
                sticker_record = retrived[0]
                # answer if user sent a duplicate
                if user_id in sticker_record.payload['users']:
                    await qdrant.close()
                    return StorageController.UploadStatus.DUPLICATE
                await qdrant.set_payload(
                    collection_name=COLLECTION,
                    payload={"users": sticker_record.payload['users'] + [user_id]},
                    points=[sticker_record.id]
                )
                await qdrant.close()
                return StorageController.UploadStatus.UPLOADED
            
            # download and embed
            url = await sticker_file_coro
            logger.debug(f"Sticker url: {url}")
            vector = await CLIPClient(REDIS).process_image(url)
            logger.debug(f"Embedding: {vector}")
            
            # save to qdrant storage
            # idk y tf they made it not async
            qdrant.upload_points(
                collection_name=COLLECTION,
                wait=False,
                points=[
                    PointStruct(
                        id=str(uuid.uuid1()),
                        vector=vector,
                        payload={
                            'users': [user_id],
                            "unique_id": unique_id,
                            "file_id": file_id,
                            "type": type,
                            "is_video": is_video,
                            "is_animated": is_animated,
                            "set_name": set_name,
                            "emoji": emoji
                        })
                ]
            )
            await qdrant.close()
            return StorageController.UploadStatus.UPLOADED
        except Exception as e:
            await qdrant.close()
            raise e
