FROM python:3.8-slim

WORKDIR /app
COPY actions.yml /app/actions.yml
COPY config.yml /app/config.yml

ARG CURATOR_VERSION=8.0.21
RUN sed -i 's@deb.debian.org@mirrors.aliyun.com@g' /etc/apt/sources.list.d/debian.sources && apt-get update && apt-get install -y cron && echo "0 0 * * * curator --config /app/config.yml /app/actions.yml" > /etc/cron.d/curator-cron && chmod 0644 /etc/cron.d/curator-cron && crontab /etc/cron.d/curator-cron && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir elasticsearch-curator==$CURATOR_VERSION

CMD ["cron", "-f"]
