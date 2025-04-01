FROM node:18-alpine

WORKDIR /app

RUN apk add --no-cache \
    chromium \
    nss \
    freetype \
    harfbuzz \
    ttf-dejavu \
    && npm install puppeteer --save \
    && npm install express body-parser --save

RUN apk add --no-cache fontconfig ttf-dejavu ttf-droid ttf-freefont wqy-zenhei

COPY app.js /app/app.js

ENV PUPPETEER_EXECUTABLE_PATH="/usr/bin/chromium"

EXPOSE 5000

CMD ["node", "app.js"]
