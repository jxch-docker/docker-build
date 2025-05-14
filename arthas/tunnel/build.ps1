docker buildx build --platform=linux/arm64,linux/amd64 --build-arg ARTHAS_VERSION=4.0.5 -t jxch/arthas-tunnel-server:4.0.5 -t jxch/arthas-tunnel-server:latest . --push
