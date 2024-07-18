from qdrant_client import QdrantClient
from qdrant_client.models import *
from tqdm import tqdm
from aiogram import Bot
import asyncio as aio
import traceback

qdrant = QdrantClient(
    url="{url}",
    api_key="{api_key}"
)

async def main():
    bot1 = Bot("{token}")
    bot2 = Bot("{token}")
    bot3 = Bot("{token}")
    bots = [bot1, bot2, bot3]
    records, offset = qdrant.scroll(
        collection_name="{old_collection}",
        limit=10,
        with_payload=True,
        with_vectors=True,
    )
    while offset is not None:
        for rec in tqdm(records):
            for bot in bots:
                try:
                    msg = await bot.send_sticker("{someone}", rec.payload['file_id'])
                    break
                except:
                    continue
            sticker = msg.sticker
            if sticker.set_name is None:
                continue
            retrived = qdrant.scroll(
                collection_name="{new_collection}",
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="unique_id", match=MatchValue(value=sticker.file_unique_id)),
                    ]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False,
            )
            retrived = retrived[0]
            if len(retrived) > 0:
                sticker_record = retrived[0]
                if rec.payload['chat_id'] in sticker_record.payload['users']:
                    continue
                qdrant.set_payload(
                    collection_name="{new_collection}",
                    payload={"users": sticker_record.payload['users'] + [rec.payload['chat_id']]},
                    points=[sticker_record.id]
                )
                continue
            qdrant.upsert(
                collection_name="{new_collection}",
                points=[PointStruct(
                    id=rec.id, vector=rec.vector,
                    payload={
                        "users": [rec.payload['chat_id']],
                        "file_id": rec.payload['file_id'],
                        "unique_id": rec.payload['unique_id'],
                        "type": sticker.type,
                        "is_video": sticker.is_video,
                        "is_animated": sticker.is_animated,
                        "set_name": sticker.set_name,
                        "emoji": sticker.emoji
                    }
                )],
                wait=False
            )
        records, offset = qdrant.scroll(
            collection_name="{old_collection}",
            limit=10,
            with_payload=True,
            with_vectors=True,
            offset=offset
        )

aio.run(main())
