FROM python:3.8-slim

WORKDIR /app

ARG CURATOR_VERSION=8.0.17
RUN pip install elasticsearch-curator==$CURATOR_VERSION

COPY actions.yml /app/actions.yml
COPY config.yml /app/config.yml

RUN apt-get update && apt-get install -y cron && echo "0 0 * * * curator --config /app/config.yml /app/actions.yml" > /etc/cron.d/curator-cron && chmod 0644 /etc/cron.d/curator-cron && crontab /etc/cron.d/curator-cron && apt-get clean && rm -rf /var/lib/apt/lists/*

CMD ["cron", "-f"]
