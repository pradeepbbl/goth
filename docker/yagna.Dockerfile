FROM python:3.8.2-alpine3.11 AS downloader
WORKDIR /
ARG GITHUB_API_TOKEN
COPY ./download_artifacts.py ./download_release.py ./
RUN pip install requests \
    && python ./download_artifacts.py -t ${GITHUB_API_TOKEN} \
    && python ./download_release.py -t ${GITHUB_API_TOKEN} ya-runtime-wasi

FROM debian:bullseye-slim
COPY default/asset /asset
COPY default/asset/presets.json /presets.json
COPY --from=downloader /yagna.deb /ya-sb-router.deb ya-runtime-wasi.deb ./
RUN apt update && apt install -y ./yagna.deb ./ya-sb-router.deb ./ya-runtime-wasi.deb
ENTRYPOINT /usr/bin/yagna
