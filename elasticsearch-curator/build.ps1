$version = Get-Content -Path "./version.txt"
docker buildx build --platform=linux/arm64,linux/amd64 -t jxch/elasticsearch-curator:$version --build-arg CURATOR_VERSION=$version . --push

