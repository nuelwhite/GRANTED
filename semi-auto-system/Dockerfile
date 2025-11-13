# ---------- BASE IMAGE ----------
FROM python:3.11-slim

# ---------- WORKDIR ----------
WORKDIR /app

# ---------- SYSTEM DEPENDENCIES ----------
RUN apt-get update && \
    apt-get install -y cron procps vim && \
    rm -rf /var/lib/apt/lists/*

# ---------- COPY PROJECT ----------
COPY . .

# ---------- INSTALL PYTHON DEPENDENCIES ----------
RUN pip install --no-cache-dir pandas pydantic python-dotenv google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2

# ---------- SETUP CRON JOB ----------
# Copy cron job file into the container
COPY cronjob /etc/cron.d/pipeline-cron

# Give execution rights on the cron job file
RUN chmod 0644 /etc/cron.d/pipeline-cron

# Ensure cron logs are written and cron reads environment paths
RUN echo "SHELL=/bin/bash" > /etc/environment && \
    echo "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" >> /etc/environment

# Create the log file to be able to run tail later
RUN touch /var/log/cron.log

# ---------- ENTRYPOINT ----------
# Start cron in the foreground and continuously stream logs
CMD ["bash", "-c", "service cron start && tail -f /var/log/cron.log"]
