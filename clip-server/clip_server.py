from os import getenv
import multiprocessing as mp
import logging
import sys
from transformers import CLIPTokenizer, CLIPTextModelWithProjection
from transformers import CLIPImageProcessor, CLIPVisionModelWithProjection
import numpy as np
from PIL import Image
from io import BytesIO
from redis import Redis
from bson import dumps, loads
from aiohttp import ClientSession
import asyncio

logger = logging.getLogger(__name__)
REDIS = getenv("REDIS_URL")
IMAGE_QUEUE = "request:images"
TEXT_QUEUE = "request:texts"
TEXT_FLAG = "request:text-flag"
REQUEST_COUNTER = "request:count"
RESPONSE_QUEUE = "response"
ERROR = "ERROR"
SUCCESS = "SUCCESS"
BATCH_SIZE = 32


async def _load_images(requests: list[dict]) -> list[dict | None]:
    """Simple (not really) function to load bunch of images with asyncio

    Attributes:
        requests (list[dict]): list of requests from "requets:images" queue
        described in redis-communication
    Returns (list[dict | None]): list of dicts with schema
    {"seq":<seq num>, "img": <PIL.Image.Image>} or Nones if couldn't load image
    """
    images = []
    # looks damn
    async def requests_url():
        for req in requests:
            yield req
    async with ClientSession() as session:
        async for req in requests_url():
            image = {'seq': req['seq']}
            try:
                async with session.get(req['url']) as response:
                    image['img'] = Image.open(BytesIO(await response.content.read()))
            except:
                image['img'] = None
            images.append(image)
    return images

def image_processor() -> None:
    """CLIP server image processor

    Handles imcoming image requests. Loads bunch of images and encodes it.
    """
    model = CLIPVisionModelWithProjection.from_pretrained("openai/clip-vit-large-patch14")
    processor = CLIPImageProcessor.from_pretrained("openai/clip-vit-large-patch14")
    while True:
        r = Redis.from_url(REDIS)
        # load up to `BATCH_SIZE` requests
        _, bson_requests = r.blmpop(0, 1, IMAGE_QUEUE, direction="RIGHT", count=BATCH_SIZE)
        requests = [loads(req) for req in bson_requests]
        # download images from urls
        downloaded = asyncio.run(_load_images(requests))
        sequence_numbers = []
        images = []
        for i in downloaded:
            # answer errorneous requests
            if not i['img']:
                r.lpush(RESPONSE_QUEUE, dumps({
                    "seq": i['seq'], "code": ERROR,
                    "answer": "Could not download image by url. Check if url is correct"
                }))
            # and prepare images
            else:
                sequence_numbers.append(i['seq'])
                images.append(i['img'])
        inputs = processor(images=images, return_tensors='pt')
        # some wierd torch magic idk
        embeddings = model(**inputs).image_embeds.cpu().detach().numpy().astype(np.float32)
        answers = [
            dumps({"seq": seq, "code": SUCCESS, "answer": embed.tobytes()})
            for seq, embed in zip(sequence_numbers, embeddings)
        ]
        r.lpush(RESPONSE_QUEUE, *answers)


def text_processor() -> None:
    """CLIP server text processor

    Handles imcoming text requests. Loads bunch of texts and encodes it.
    """
    model = CLIPTextModelWithProjection.from_pretrained("openai/clip-vit-large-patch14")
    tokenizer = CLIPTokenizer.from_pretrained("openai/clip-vit-large-patch14")
    while True:
        r = Redis.from_url(REDIS)
        # load up to `BATCH_SIZE` requests
        r.blpop(TEXT_FLAG)
        bson_requests = r.hgetall(TEXT_QUEUE)
        requests = [loads(req) for req in bson_requests.values()]
        texts = [req['text'] for req in requests]
        sequence_numbers = [req['seq'] for req in requests]
        inputs = tokenizer(texts, padding=True, return_tensors='pt')
        # some wierd torch magic idk
        embeddings = model(**inputs).image_embeds.cpu().detach().numpy().astype(np.float32)
        answers = [
            dumps({"seq": seq, "code": SUCCESS, "answer": embed.tobytes()})
            for seq, embed in zip(sequence_numbers, embeddings)
        ]
        r.lpush(RESPONSE_QUEUE, *answers)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    # image and text processors are independent, so they are working simultaneously
    img = mp.Process(target=image_processor, daemon=True)
    txt = mp.Process(target=text_processor, daemon=True)
    img.start()
    txt.start()
    img.join()
    txt.join()
