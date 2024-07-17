from os import getenv
import multiprocessing as mp
import logging
import traceback
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

REDIS = getenv("REDIS_URL")
IMAGE_QUEUE = "request:images"
TEXT_QUEUE = "request:texts"
TEXT_FLAG = "request:text-flag"
REQUEST_COUNTER = "request:count"
RESPONSE_QUEUE = "response"
ERROR = "ERROR"
SUCCESS = "SUCCESS"
IMG_BATCH_SIZE = int(getenv("IMG_BATCH_SIZE"))
TXT_BATCH_SIZE = int(getenv("TXT_BATCH_SIZE"))


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
    logger = logging.getLogger("images")
    logger.info("Loading image model")
    model = CLIPVisionModelWithProjection.from_pretrained("openai/clip-vit-large-patch14")
    processor = CLIPImageProcessor.from_pretrained("openai/clip-vit-large-patch14")
    logger.info("Image processor ready!")
    while True:
        r = Redis.from_url(REDIS)
        try:
            # load up to `IMG_BATCH_SIZE` requests
            _, bson_requests = r.blmpop(0, 1, IMAGE_QUEUE, direction="RIGHT", count=IMG_BATCH_SIZE)
            logger.info(f"Recieved {len(bson_requests)} image requests")
            if len(bson_requests) <= 0:
                continue
            requests = [loads(req) for req in bson_requests]
            # download images from urls
            downloaded = asyncio.run(_load_images(requests))
            sequence_numbers = []
            images = []
            for i in range(len(downloaded)):
                # answer errorneous requests
                if not downloaded[i]['img']:
                    r.publish(RESPONSE_QUEUE, dumps({
                        "seq": downloaded[i]['seq'], "code": ERROR,
                        "answer": "Could not download image by url. Check if url is correct"
                    }))
                    logger.warning(f"Bad url: {requests[i]['seq']}")
                # and prepare images
                else:
                    sequence_numbers.append(downloaded[i]['seq'])
                    images.append(downloaded[i]['img'])
            logger.info(f"Processing {len(images)} images")
            inputs = processor(images=images, return_tensors='pt')
            logger.debug("Images prepocessed")
            # some wierd torch magic idk
            embeddings = model(**inputs).image_embeds.cpu().detach().numpy().astype(np.float32)
            logger.debug("Images embedded")
            answers = [
                dumps({"seq": seq, "code": SUCCESS, "answer": embed.tobytes()})
                for seq, embed in zip(sequence_numbers, embeddings)
            ]
            for ans in answers:
                r.publish(RESPONSE_QUEUE, ans)
            logger.debug("Requests answered")
            logger.info(f"{len(answers)} images successfully embedded")
        except:
            logger.error(traceback.format_exc())
        finally:
            r.close()


def text_processor() -> None:
    """CLIP server text processor

    Handles imcoming text requests. Loads bunch of texts and encodes it.
    """
    logger = logging.getLogger("texts")
    logger.info("Loading text model")
    model = CLIPTextModelWithProjection.from_pretrained("openai/clip-vit-large-patch14")
    tokenizer = CLIPTokenizer.from_pretrained("openai/clip-vit-large-patch14")
    logger.info("Text processor ready!")
    while True:
        r = Redis.from_url(REDIS)
        try:
            bson_requests = r.hgetall(TEXT_QUEUE)
            if len(bson_requests) <= 0:
                # uhhh... fuck you Redis!
                p = r.pubsub(ignore_subscribe_messages=True)
                p.subscribe(TEXT_FLAG)
                p.listen().__next__()
                p.unsubscribe()
                p.close()
            bson_requests = r.hgetall(TEXT_QUEUE)
            if len(bson_requests) <= 0:
                continue
            logger.info(f"Recieved {len(bson_requests)} text requests")
            
            requests = [loads(req) for req in bson_requests.values()]
            for i in range(TXT_BATCH_SIZE):
                requests_slice = requests[i*TXT_BATCH_SIZE:(i+1)*TXT_BATCH_SIZE]
                texts = [req['text'] for req in requests_slice]
                sequence_numbers = [req['seq'] for req in requests_slice]
                logger.info(f"Processing {len(texts)} texts")
                inputs = tokenizer(texts, padding=True, return_tensors='pt')
                logger.debug("Texts prepocessed")
                # some wierd torch magic idk
                embeddings = model(**inputs).text_embeds.cpu().detach().numpy().astype(np.float32)
                logger.debug("Texts embedded")
                answers = [
                    dumps({"seq": seq, "code": SUCCESS, "answer": embed.tobytes()})
                    for seq, embed in zip(sequence_numbers, embeddings)
                ]
                for ans in answers:
                    r.publish(RESPONSE_QUEUE, ans)
                logger.debug("Requests answered")
                logger.info(f"{len(answers)} texts successfully embedded")
        except:
            logger.error(traceback.format_exc())
        finally:
            r.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    # image and text processors are independent, so they are working simultaneously
    img = mp.Process(target=image_processor, daemon=True)
    txt = mp.Process(target=text_processor, daemon=True)
    img.start()
    txt.start()
    img.join()
    txt.join()
