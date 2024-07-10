from os import getenv
from json import dumps
from pickle import loads
from asyncio import Event
import logging

from redis.asyncio import Redis, ConnectionPool

logger = logging.getLogger(__name__)
REDIS = getenv("REDIS_URL")
IMAGE_QUEUE = "request:images"
REQUEST_COUNTER = "request:count"

class CLIPClient:
    """Client for interacting with CLIP server via Redis

    Singleton class that accepts requests for CLIP and listens
    for incoming responses
    """

    async def process_image(self, image_url: str) -> list[float]:
        """Sends image processing request
        Attributes:
            image_url (str): url of an image with which we can download an
            image on the server side
        Returns: list of floats - embedding vector of an image
        Raises:
            CLIPServerException: raises when server returns error code, may
            happen if image_url was bad
        """
        redis = Redis.from_pool(self._pool)
        seq = await redis.incr(REQUEST_COUNTER)
        request = self._Request()
        self._requests[seq] = request
        await redis.lpush(IMAGE_QUEUE, dumps({"seq": seq, "url": image_url}))
        logger.debug(f"Sent process_image request with seq={seq}")
        await request.event.wait()
        response = request.answer
        logger.debug(f"Recieved reqponse for process_image seq={seq}, "
                     f"answer={response}")
        if response['code'] == 'ERROR':
            raise CLIPServerException(response['answer'])
        return response['embedding']


    async def process_text(self, text: str) -> list[float]:
        """Sends text processing request
        
        Attributes:
            text (str): text to encode
        Returns: list of floats - embedding vector of a text
        Raises:
            CLIPServerException: raises when server returns error code
        """
        pass


    # Singleton
    _instance = None
    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    

    def __init__(self) -> None:
        self._pool = ConnectionPool.from_url(REDIS)
        # pending requests
        self._requests = {}
        # Here we create new task that listens for incoming responses on redis
        pass


    class _Request:
        """Class for response delivering
        """
        def __init__(self) -> None:
            self._event = Event()
            self._answer: dict = None
        

        def answer(self) -> dict:
            # TODO: пропиши константы кодов ответов
            # TODO: этот класс
            # TODO: поправь process_image
            # TODO: можешь здесь же добавить логику парсинга ответа
            # И даже добавить сюда логику дампа реквеста и его отправки
            pass


        def response(self, answer: bytes) -> None:
            """Sets the _Request event

            Attributes:
                answer (bytes): 
            """
            self._answer = answer
            self._event.set()


class CLIPServerException(Exception):
    """Simple exception class for errors happend on CLIP server side
    """
    def __init__(self, server_response: str) -> None:
        super().__init__(
            "Internal server error, CLIP server says: " + server_response
        )
