# Containerized setup for the system

FROM python:3.9-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONBUFFERED=1

CMD [ "python", "extract_grans.py" ]