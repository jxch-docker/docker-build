FROM surnet/alpine-wkhtmltopdf:3.21.2-0.12.6-full

WORKDIR /app

RUN apk add --no-cache python3 py3-pip && python3 -m venv /venv && /venv/bin/pip install --upgrade pip && /venv/bin/pip install flask pdfkit
RUN apk add --no-cache fontconfig ttf-dejavu ttf-droid ttf-freefont wqy-zenhei


COPY app.py app.py

EXPOSE 5000

ENV PATH="/venv/bin:$PATH"
ENV FLASK_APP="/app/app.py"

ENTRYPOINT ["/venv/bin/python3", "-m", "flask", "run", "--host=0.0.0.0", "--port=5000"]
