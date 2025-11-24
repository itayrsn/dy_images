FROM python:3.10-slim
WORKDIR /app
RUN pip install aiohttp aiofiles aio-pika
COPY main.py .
CMD ["uv", "run", "main.py"]