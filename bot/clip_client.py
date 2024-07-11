from os import getenv
import logging
from bson import loads, dumps
from asyncio import Event, create_task, Task, gather
from numpy import frombuffer, float32
from numpy.typing import ArrayLike
from redis.asyncio import Redis


logger = logging.getLogger(__name__)
IMAGE_QUEUE = "request:images"
TEXT_QUEUE = "request:texts"
TEXT_FLAG = "request:text-flag"
REQUEST_COUNTER = "request:count"
RESPONSE_QUEUE = "response"

class CLIPClient:
    """Client for interacting with CLIP server via Redis

    Singleton class that accepts requests for CLIP and listens
    for incoming responses
    """

    async def process_image(self, image_url: str) -> ArrayLike:
        """Sends image processing request
        Attributes:
            image_url (str): url of an image with which we can download an
            image on the server side
        Returns: list of floats - embedding vector of an image
        Raises:
            CLIPServerException: raises when server returns error code, may
            happen if image_url was bad
        """
        redis = Redis.from_url(self._redis_url)
        seq = await redis.incr(REQUEST_COUNTER)
        request = _Request(seq)
        self._requests[seq] = request
        await redis.lpush(IMAGE_QUEUE, dumps({"seq": seq, "url": image_url}))
        await redis.aclose()
        logger.debug(f"Sent process_image request with seq={seq}")
        await request.event.wait()
        response = request.answer
        logger.debug(f"Recieved reqponse for process_image seq={seq}, "
                     f"answer={response}")
        if response['code'] == 'ERROR':
            raise CLIPServerException(response['answer'])
        return frombuffer(response['answer'], dtype=float32)


    async def process_text(self, id: str, text: str) -> ArrayLike:
        """Sends text processing request
        
        Attributes:
            id (str): unique id of text request thread - see docs/redis-communication.md
            text (str): text to encode
        Returns: list of floats - embedding vector of a text
        Raises:
            CLIPServerException: raises when server returns error code
        """
        redis = Redis.from_url(self._redis_url)
        seq = await redis.incr(REQUEST_COUNTER)
        request = _Request(seq)
        self._requests[seq] = request
        await gather(
            redis.hset(
                TEXT_QUEUE,
                key=id,
                value=dumps({"seq": seq, "text": text})
            ),
            redis.lset(TEXT_FLAG, 0, "available")
        )
        await redis.aclose()
        logger.debug(f"Sent process_text request with seq={seq}")
        await request.event.wait()
        response = request.answer
        logger.debug(f"Recieved reqponse for process_text seq={seq}, "
                     f"answer={response}")
        if response['code'] == 'ERROR':
            raise CLIPServerException(response['answer'])
        return frombuffer(response['answer'], dtype=float32)


    # Singleton
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._requests = {}
        # Here we create new task that listens for incoming responses on redis
        async def listener():
            r = Redis.from_url(self._redis_url)
            try:
                while True:
                    _, banswer = await r.brpop(RESPONSE_QUEUE)
                    answer = loads(banswer)
                    logger.debug(f"Catch CLIP server response seq={answer['seq']}")
                    req: _Request = self._requests[answer['seq']]
                    req.response(answer)
            finally:
                await r.aclose()
                logger.info("CLIP server reponse listening stopped properly")
        self._listener_task: Task = create_task(listener())
        logger.info("Started listening for CLIP server reponses")


    def __del__(self):
        self._listener_task.cancel()


class _Request:
    """Class for response delivering
    """
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"
    def __init__(self, seq: int) -> None:
        self.event = Event()
        self.answer: dict = {
            "seq": seq,
            "code": self.ERROR,
            "answer": "Request not waited!"
        }
    

    def response(self, answer: dict) -> None:
        """Sets the _Request event

        Attributes:
            answer (bytes): BSON encoded response from Redis
        """
        self.answer = answer
        self.event.set()


class CLIPServerException(Exception):
    """Simple exception class for errors happend on CLIP server side
    """
    def __init__(self, server_response: str) -> None:
        super().__init__(
            "Internal server error, CLIP server says: " + server_response
        )
