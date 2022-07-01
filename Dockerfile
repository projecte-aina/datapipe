FROM python:3.9.7-slim-buster

RUN apt-get update && apt-get install --no-install-recommends -y ffmpeg bash curl git && \
     rm -rf /var/lib/{apt,dpkg,cache,log}

RUN curl -fsSL https://deb.nodesource.com/setup_16.x | bash -
RUN apt-get install -y nodejs
RUN npm install --location=global nodemon

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN mkdir -p /app

RUN groupadd --gid 1001 --system datapipe && \
  useradd --system --uid 1001 --gid 1001 datapipe && \
  chown -R 1001:1001 /opt/venv && \
  chown -R 1001:1001 /app

USER 1001:1001

WORKDIR /app

COPY requirements.txt .
# remove torch as we want to install cpu-only linux wheel
# RUN sed -i '/torch/d' requirements.txt

RUN pip install --no-cache-dir -r requirements.txt
  # pip install https://download.pytorch.org/whl/cpu/torch-1.10.1%2Bcpu-cp39-cp39-linux_x86_64.whl

COPY . .

ENTRYPOINT [ "python", "-m" ]





