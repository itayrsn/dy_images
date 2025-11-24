import os
import json
import asyncio
import uuid
import aio_pika
import aiohttp
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct


# Config
MQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8001")
INDEX_QUEUE = "indexing_queue"
IMG_COLLECTION_NAME = "images"
EMBEDDING_SIZE = 512

# Init Qdrant
client = QdrantClient(host=QDRANT_HOST, port=6333)

def ensure_collection():
    client.recreate_collection(
            collection_name=IMG_COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBEDDING_SIZE, distance=Distance.COSINE))


async def get_embedding(image_path):
    """Calls embedding generator service to get embedding"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{EMBEDDING_SERVICE_URL}/embed",
                json={"image_path": image_path},
            ) as resp:
                data = await resp.json()
                if "embedding" in data:
                    return data["embedding"]
                print(f"Model Error: {data}")
    except Exception as e:
        print(f"Connection Error to Model Server: {e}")
    return None


async def process_message(message: aio_pika.IncomingMessage):
    async with message.process():
        body = message.body.decode()
        src_url, path = json.loads(body).values()
        vector = await get_embedding(path)
        
        if vector:
            # use image source url's hash as ID
            vector_id = uuid.uuid5(uuid.NAMESPACE_URL, src_url)
            
            client.upsert(
                collection_name=IMG_COLLECTION_NAME,
                points=[PointStruct(
                    id=vector_id,
                    vector=vector,
                    payload={"path": path, "src_url": src_url}
                )])


async def main():
    ensure_collection()
    
    connection = await aio_pika.connect_robust(f"amqp://guest:guest@{MQ_HOST}/")
    channel = await connection.channel()
    queue = await channel.declare_queue(INDEX_QUEUE, auto_delete=True)
    
    await queue.consume(process_message)
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())