docker buildx build --platform=linux/arm64,linux/amd64 -t jxch/snowflake:go-1.0.0 -t jxch/snowflake:go -t jxch/snowflake:latest . --push
