FROM python:3.9.7-slim-buster

RUN apt-get update && apt-get install --no-install-recommends -y ffmpeg bash curl && \
    rm -rf /var/lib/{apt,dpkg,cache,log}

WORKDIR /app

COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN addgroup --gid 1001 --system datapipe && \
  adduser --system --uid 1001 --gid 1001 datapipe && \
  chown -R 1001:1001 /opt/venv

USER 1001:1001

ENTRYPOINT [ "python", "-m" ]