"""
Load Balancer for Task 3.

Responsibilities:
  - Maintain N server containers using consistent hashing
  - Route /<path> requests to the right server replica
  - Expose /rep, /add, /rm management endpoints
  - Detect failed servers (via /heartbeat) and spawn replacements automatically
"""

import os
import time
import random
import string
import threading

import requests
from flask import Flask, request, jsonify

from consistent_hash import ConsistentHashMap

app = Flask(__name__)

# ---------- Configuration (defaults match Task 2 spec) ----------
N_SERVERS = int(os.environ.get("N_SERVERS", 3))
DOCKER_NETWORK = os.environ.get("DOCKER_NETWORK", "net1")
SERVER_IMAGE = os.environ.get("SERVER_IMAGE", "server_image:latest")
HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", 5))  # seconds

# ---------- Shared state ----------
hash_map = ConsistentHashMap()
# replicas: hostname -> numeric server_id (used for hashing)
replicas = {}
replicas_lock = threading.Lock()
next_server_id = 1  # increasing counter so every server gets a unique numeric id


# ---------- Docker helpers ----------

def docker_run_server(hostname: str, server_label: str):
    """Spawns a new server container with given hostname, attached to our network."""
    cmd = (
        f"docker run -d --name {hostname} --network {DOCKER_NETWORK} "
        f"--network-alias {hostname} -e SERVER_ID={server_label} {SERVER_IMAGE}"
    )
    result = os.popen(cmd).read()
    return len(result.strip()) > 0


def docker_remove_server(hostname: str):
    """Stops and removes a server container."""
    os.system(f"docker stop {hostname} >/dev/null 2>&1 && docker rm {hostname} >/dev/null 2>&1")


def random_hostname():
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"S{suffix}"


# ---------- Core replica management ----------

def _add_replica_locked(hostname: str):
    """Caller must hold replicas_lock."""
    global next_server_id
    server_id = next_server_id
    next_server_id += 1
    ok = docker_run_server(hostname, hostname)
    if ok:
        replicas[hostname] = server_id
        hash_map.add_server(hostname, server_id)
    return ok


def _remove_replica_locked(hostname: str):
    """Caller must hold replicas_lock."""
    if hostname in replicas:
        hash_map.remove_server(hostname)
        del replicas[hostname]
        docker_remove_server(hostname)


def initialize_replicas(n: int):
    with replicas_lock:
        for _ in range(n):
            hostname = random_hostname()
            _add_replica_locked(hostname)


# ---------- Heartbeat / failure detection (background thread) ----------

def heartbeat_monitor():
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        with replicas_lock:
            current_hosts = list(replicas.keys())

        for hostname in current_hosts:
            try:
                resp = requests.get(f"http://{hostname}:5000/heartbeat", timeout=2)
                alive = resp.status_code == 200
            except requests.exceptions.RequestException:
                alive = False

            if not alive:
                with replicas_lock:
                    if hostname in replicas:  # still present, hasn't been removed already
                        print(f"[heartbeat] {hostname} is down. Removing and respawning...")
                        _remove_replica_locked(hostname)
                        new_hostname = random_hostname()
                        _add_replica_locked(new_hostname)


# ---------- Endpoints ----------

@app.route("/rep", methods=["GET"])
def get_replicas():
    with replicas_lock:
        hostnames = list(replicas.keys())
    return jsonify({
        "message": {
            "N": len(hostnames),
            "replicas": hostnames
        },
        "status": "successful"
    }), 200


@app.route("/add", methods=["POST"])
def add_replicas():
    payload = request.get_json(silent=True) or {}
    n = payload.get("n")
    hostnames_requested = payload.get("hostnames", [])

    if n is None or not isinstance(n, int) or n <= 0:
        return jsonify({"message": "<Error> 'n' must be a positive integer", "status": "failure"}), 400

    if len(hostnames_requested) > n:
        return jsonify({
            "message": "<Error> Length of hostname list is more than newly added instances",
            "status": "failure"
        }), 400

    with replicas_lock:
        # use provided hostnames first, then fill the rest randomly
        to_add = list(hostnames_requested)
        while len(to_add) < n:
            to_add.append(random_hostname())

        for hostname in to_add:
            _add_replica_locked(hostname)

        all_hosts = list(replicas.keys())

    return jsonify({
        "message": {
            "N": len(all_hosts),
            "replicas": all_hosts
        },
        "status": "successful"
    }), 200


@app.route("/rm", methods=["DELETE"])
def remove_replicas():
    payload = request.get_json(silent=True) or {}
    n = payload.get("n")
    hostnames_requested = payload.get("hostnames", [])

    if n is None or not isinstance(n, int) or n <= 0:
        return jsonify({"message": "<Error> 'n' must be a positive integer", "status": "failure"}), 400

    if len(hostnames_requested) > n:
        return jsonify({
            "message": "<Error> Length of hostname list is more than removable instances",
            "status": "failure"
        }), 400

    with replicas_lock:
        if n > len(replicas):
            return jsonify({
                "message": "<Error> Not enough replicas to remove",
                "status": "failure"
            }), 400

        to_remove = list(hostnames_requested)
        remaining_pool = [h for h in replicas.keys() if h not in to_remove]
        random.shuffle(remaining_pool)

        while len(to_remove) < n:
            to_remove.append(remaining_pool.pop())

        for hostname in to_remove:
            _remove_replica_locked(hostname)

        all_hosts = list(replicas.keys())

    return jsonify({
        "message": {
            "N": len(all_hosts),
            "replicas": all_hosts
        },
        "status": "successful"
    }), 200


@app.route("/<path:subpath>", methods=["GET"])
def route_request(subpath):
    with replicas_lock:
        if not replicas:
            return jsonify({"message": "<Error> No server replicas available", "status": "failure"}), 400

    # generate a 6-digit request id, per the spec
    request_id = random.randint(100000, 999999)
    target_hostname = hash_map.get_server_for_request(request_id)

    if target_hostname is None:
        return jsonify({"message": "<Error> Could not route request", "status": "failure"}), 400

    try:
        resp = requests.get(f"http://{target_hostname}:5000/{subpath}", timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except requests.exceptions.RequestException:
        return jsonify({
            "message": f"<Error> '/{subpath}' endpoint does not exist in server replicas",
            "status": "failure"
        }), 400


if __name__ == "__main__":
    initialize_replicas(N_SERVERS)
    monitor_thread = threading.Thread(target=heartbeat_monitor, daemon=True)
    monitor_thread.start()
    app.run(host="0.0.0.0", port=5000)
