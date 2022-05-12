FROM python:3.9.7-slim-buster

RUN apt-get update && apt-get install --no-install-recommends -y ffmpeg bash curl git && \
    rm -rf /var/lib/{apt,dpkg,cache,log}

WORKDIR /app

COPY requirements.txt .
# remove torch as we want to install cpu-only linux wheel
# RUN sed -i '/torch/d' requirements.txt

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir -r requirements.txt
  # pip install https://download.pytorch.org/whl/cpu/torch-1.10.1%2Bcpu-cp39-cp39-linux_x86_64.whl

COPY . .

RUN addgroup --gid 1001 --system datapipe && \
  adduser --system --uid 1001 --gid 1001 datapipe && \
  chown -R 1001:1001 /opt/venv

USER 1001:1001

ENTRYPOINT [ "python", "-m" ]