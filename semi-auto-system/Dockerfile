# Containerized setup for the system

FROM python:3.9-slim

WORKDIR /app

COPY . /app

RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pandas pydantic python-dotenv google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2

COPY cronjob /etc/cron.d/pipeline-cron

RUN chmod 0644 /etc/cron.d/pipeline-cron

RUN crontab /etc/cron.d/pipeline-cron

RUN touch /var/log/cron.log

ENV PYTHONBUFFERED=1

CMD cron && tail -f /var/log/cron.log