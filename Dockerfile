FROM python:3.12.3

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD uvicorn app:asgi --host 0.0.0.0 --port ${PORT:-5000}
