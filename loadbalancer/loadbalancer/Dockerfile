FROM python:3.11-slim

WORKDIR /app

# Install the docker CLI so this container can talk to the host's docker daemon
# (the daemon socket is mounted in via docker-compose.yml)
RUN apt-get update && \
    apt-get install -y --no-install-recommends docker.io && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY consistent_hash.py loadbalancer.py ./

EXPOSE 5000

CMD ["python", "loadbalancer.py"]
