from os import getenv
import logging
import traceback

from qdrant_client.async_qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

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

    async def search(user_id: str, text: str, limit: int=50, timeout: float | None=60) -> list[str]:
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
