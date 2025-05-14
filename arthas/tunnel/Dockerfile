FROM openjdk:8-jre-alpine

LABEL maintainer="xicheng.jiang.1@gmail.com"
LABEL app="arthas-tunnel-server"
LABEL version="1.0"

WORKDIR /opt

# Arthas 版本号（可在构建时通过 --build-arg ARTHAS_VERSION=xxx 覆盖）
ARG ARTHAS_VERSION=4.0.5
ENV ARTHAS_VERSION=${ARTHAS_VERSION}

# 安装 unzip 和 wget
RUN apk add --no-cache unzip wget

# 直接下载 Arthas Tunnel Server fatjar 和 bin 包，均用版本变量
ADD https://github.com/alibaba/arthas/releases/download/arthas-all-${ARTHAS_VERSION}/arthas-tunnel-server-${ARTHAS_VERSION}-fatjar.jar /opt/arthas-tunnel-server.jar
ADD https://github.com/alibaba/arthas/releases/download/arthas-all-${ARTHAS_VERSION}/arthas-bin.zip /opt/arthas-bin.zip

RUN mkdir -p /opt/arthas-bin \
    && unzip /opt/arthas-bin.zip -d /opt/arthas-bin \
    && rm /opt/arthas-bin.zip
RUN apk add curl

# 暴露 WebSocket 端口和 actuator 健康端口
EXPOSE 7777
EXPOSE 8080

# 支持配置文件挂载与环境变量安全注入
ENV ARTHAS_TOKEN=535e65a6-e4ea-4c97-aa94-f6c0541cf59f
ENV USERNAME=arthas
ENV PASSWORD=arthas

HEALTHCHECK --interval=30s --timeout=10s --start-period=300s CMD curl -f -u ${USERNAME}:${PASSWORD} http://127.0.0.1:8080/actuator/health || exit 1

# 启动命令，支持自定义token与额外参数
ENTRYPOINT [ "sh", "-c", "java -jar /opt/arthas-tunnel-server.jar --arthas.token=${ARTHAS_TOKEN} --spring.security.user.name=${USERNAME} --spring.security.user.password=${PASSWORD}" ]
