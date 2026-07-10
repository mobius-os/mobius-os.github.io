FROM python:3.12-slim

WORKDIR /app

ARG MOBIUS_LAUNCH_SOURCE_REPO=mobius-os/mobius-os.github.io
ARG MOBIUS_LAUNCH_SOURCE_PATH=services/mobius_launch
ARG MOBIUS_LAUNCH_GIT_SHA=unknown
ARG MOBIUS_LAUNCH_IMAGE_REF=

ENV MOBIUS_LAUNCH_SOURCE_REPO=$MOBIUS_LAUNCH_SOURCE_REPO
ENV MOBIUS_LAUNCH_SOURCE_PATH=$MOBIUS_LAUNCH_SOURCE_PATH
ENV MOBIUS_LAUNCH_GIT_SHA=$MOBIUS_LAUNCH_GIT_SHA
ENV MOBIUS_LAUNCH_IMAGE_REF=$MOBIUS_LAUNCH_IMAGE_REF

LABEL org.opencontainers.image.source="https://github.com/${MOBIUS_LAUNCH_SOURCE_REPO}" \
      org.opencontainers.image.revision="${MOBIUS_LAUNCH_GIT_SHA}" \
      org.opencontainers.image.title="Mobius Launch"

RUN pip install --no-cache-dir flask cryptography gunicorn

COPY app.py /app/app.py
COPY static /app/static

EXPOSE 8080

CMD ["gunicorn", "-b", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "app:app"]
