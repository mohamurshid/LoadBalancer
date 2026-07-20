FROM python:3.11-slim

WORKDIR /app

# Install a standalone Docker CLI binary so this container can talk to
# the host Docker daemon through the mounted socket.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl tar && \
    curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.5.1.tgz -o /tmp/docker.tgz && \
    tar -xzf /tmp/docker.tgz -C /tmp && \
    mv /tmp/docker/docker /usr/local/bin/docker && \
    chmod +x /usr/local/bin/docker && \
    rm -rf /tmp/docker /tmp/docker.tgz /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY consistent_hash.py loadbalancer.py ./

EXPOSE 5000

CMD ["python", "loadbalancer.py"]
