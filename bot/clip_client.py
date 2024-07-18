from os import getenv
import logging
from bson import loads, dumps
from asyncio import Event, create_task, Task, wait_for
from numpy import frombuffer, float32
from numpy.typing import ArrayLike
from redis.asyncio import Redis, WatchError
import traceback


logger = logging.getLogger(__name__)
IMAGE_QUEUE = "request:images"
TEXT_QUEUE = "request:texts"
TEXT_FLAG = "request:text-flag"
REQUEST_COUNTER = "request:count"
RESPONSE_QUEUE = "response"

def _singleton(class_):
    instances = {}
    def getinstance(*args, **kwargs):
        if class_ not in instances:
            instances[class_] = class_(*args, **kwargs)
        return instances[class_]
    return getinstance

@_singleton
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


    async def process_text(self, id: str, text: str, timeout: float | None = None) -> ArrayLike:
        """Sends text processing request
        
        Attributes:
            id (str): unique id of text request thread - see docs/redis-communication.md
            text (str): text to encode
            timeout (float | None): timeout to wait after sending request
        Returns: list of floats - embedding vector of a text
        Raises:
            CLIPServerException: raises when server returns error code
            TimeoutError: raises when timeout is set and text didn't process
            within this timeout
        """
        redis = Redis.from_url(self._redis_url)
        seq = await redis.incr(REQUEST_COUNTER)
        request = _Request(seq)
        self._requests[seq] = request
        await redis.hset(
            TEXT_QUEUE,
            key=id,
            value=dumps({"seq": seq, "text": text})
        )
        await redis.publish(TEXT_FLAG, "available")
        await redis.aclose()
        logger.debug(f"Sent process_text request with seq={seq}")
        try:
            await wait_for(request.event.wait(), timeout)
        except TimeoutError:
            with redis.pipeline(transaction=True) as pipe:
                while True:
                    try:
                        await pipe.watch(TEXT_QUEUE)
                        query = await pipe.hget(TEXT_QUEUE, id)
                        pipe.multi()
                        if query is not None and loads(query)['seq'] == seq:
                            await pipe.hdel(TEXT_QUEUE, id)
                        await pipe.execute()
                        break
                    except WatchError:
                        continue
            raise TimeoutError()
        response = request.answer
        logger.debug(f"Recieved reqponse for process_text seq={seq}, "
                     f"answer={response}")
        if response['code'] == 'ERROR':
            raise CLIPServerException(response['answer'])
        return frombuffer(response['answer'], dtype=float32)
    

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._requests = {}
        # Here we create new task that listens for incoming responses on redis
        async def listener():
            r = Redis.from_url(self._redis_url)
            p = r.pubsub(ignore_subscribe_messages=True)
            try:
                await p.subscribe(RESPONSE_QUEUE)
                while True:
                    gen = p.listen()
                    resp = await gen.__anext__()
                    banswer = resp['data']
                    answer = loads(banswer)
                    logger.debug(f"Catch CLIP server response seq={answer['seq']}")
                    if answer['seq'] not in self._requests.keys():
                        logger.debug("Recieved answer with invalid seq (no request to answer)")
                        continue
                    req: _Request = self._requests.pop(answer['seq'])
                    req.response(answer)
            except:
                logger.error(traceback.format_exc())
            finally:
                await p.unsubscribe()
                await p.close()
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
