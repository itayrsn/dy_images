import os
import logging
import uuid
import json
import asyncio
import aiohttp
import aiofiles
import aio_pika
from pathlib import Path
from urllib.parse import urlparse
from tqdm.asyncio import tqdm

INPUT_URLS_FILE = os.getenv("INPUT_URLS_FILE", "image_urls.txt")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "../images")
MQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
INDEX_QUEUE = 'indexing_queue'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def download_image(session, url, mq_channel):
    try:
        async with session.get(url) as resp:
            resp.raise_for_status()
            content = await resp.read()

        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        _, extension = os.path.splitext(parsed.path)

        # check extension string instead of a more robust image format detection
        if extension not in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif']:
            raise ValueError(f"Unsupported image format: {extension}")

        filename = f'{uuid.uuid5(uuid.NAMESPACE_URL, url)}.{extension}'
        filepath = os.path.join(OUTPUT_DIR, filename)

        async with aiofiles.open(filepath, "wb") as f:
            await f.write(content)

    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
    else:
        try:
            await mq_channel.default_exchange.publish(
                message=aio_pika.Message(
                    body=json.dumps({'src_url': url, 'path': filepath}).encode()),
                    routing_key=INDEX_QUEUE)
        except Exception as e:
            logger.error(f"Failed to send {url} to indexing queue: {e}")


async def download_images(urls, mq_channel):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    async with aiohttp.ClientSession() as session:
        tasks = [download_image(session, url, mq_channel) for url in urls]
        await tqdm.gather(*tasks, desc="Downloading images", unit="img")


def load_urls(urls_file: Path) -> list[str]:
    with open(urls_file, "r") as f:
        return set([line.strip() for line in f.readlines()])


async def main():
    # Connect to RabbitMQ
    connection = await aio_pika.connect_robust(f"amqp://guest:guest@{MQ_HOST}/")
    channel = await connection.channel()

    # Declare queue for indexing
    await channel.declare_queue(INDEX_QUEUE, auto_delete=True)

    urls = load_urls(INPUT_URLS_FILE)
    await download_images(urls, channel)
    await connection.close()
    logger.info(f"Downloaded {len(urls)} images to {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())