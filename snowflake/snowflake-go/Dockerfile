# 构建阶段使用 Golang 官方镜像
FROM golang:1.20-alpine AS builder

ENV GOPROXY="https://goproxy.cn,direct"
WORKDIR /app

# 复制 go.mod 与 go.sum 并下载依赖
COPY go.mod go.sum ./
RUN go mod download

# 复制整个项目代码
COPY . .

# 编译生成静态二进制文件
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o app .

# 运行阶段使用轻量级 Alpine 镜像
FROM alpine:latest
WORKDIR /app

# 从构建阶段复制构建好的二进制文件
COPY --from=builder /app/app .

EXPOSE 8080

ENTRYPOINT ["./app"]