from transformers import AutoTokenizer, CLIPTextModelWithProjection
from transformers import AutoProcessor, CLIPVisionModelWithProjection
import multiprocessing as mp
from redis import Redis
# from PIL import Image
# import io
from os import getenv

REDIS = getenv("REDIS_URL")


def image_processor() -> None:
    model = CLIPVisionModelWithProjection.from_pretrained("openai/clip-vit-large-patch14")
    processor = AutoProcessor.from_pretrained("openai/clip-vit-large-patch14")
    pass


def text_processor() -> None:
    pass


if __name__ == "__main__":
    img = mp.Process(target=image_processor, daemon=True)
    txt = mp.Process(target=text_processor, daemon=True)
    img.start()
    txt.start()
    img.join()
    txt.join()
