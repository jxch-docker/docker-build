功能：
1. url静态页面转pdf（必须是静态页面）

```yml
services:
  wkhtmltopdf-flask:
    image: jxch/wkhtmltopdf-flask
    ports:
      - "5000:5000"
```

```bash
curl --location 'http://127.0.0.1:5000/pdf' \
--header 'Content-Type: application/json' \
--data '{
    "url":"https://www.baidu.com"
}'
```
