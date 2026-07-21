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
from flask import Flask, request, jsonify, render_template_string

from consistent_hash import ConsistentHashMap

app = Flask(__name__)

DASHBOARD_HTML = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Load Balancer Dashboard</title>
    <style>
        :root {
            --ink: #102a43;
            --bg: #f5efe6;
            --card: #fffdf9;
            --accent: #007f5f;
            --accent-2: #ff7d00;
            --danger: #c1121f;
            --muted: #5c677d;
            --ring: rgba(0, 127, 95, 0.25);
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            min-height: 100vh;
            font-family: "Trebuchet MS", "Segoe UI", sans-serif;
            color: var(--ink);
            background:
                radial-gradient(circle at 20% 0%, #ffe8b6 0%, transparent 50%),
                radial-gradient(circle at 80% 100%, #b9fbc0 0%, transparent 45%),
                var(--bg);
        }

        .page {
            max-width: 980px;
            margin: 0 auto;
            padding: 24px;
        }

        h1 {
            margin: 8px 0;
            font-size: clamp(1.7rem, 4vw, 2.5rem);
            letter-spacing: 0.03em;
        }

        .subtitle {
            color: var(--muted);
            margin-bottom: 20px;
        }

        .grid {
            display: grid;
            gap: 14px;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        }

        .card {
            background: var(--card);
            border: 2px solid #ece6da;
            border-radius: 14px;
            padding: 14px;
            box-shadow: 0 6px 18px rgba(16, 42, 67, 0.06);
        }

        .label {
            font-size: 0.8rem;
            text-transform: uppercase;
            color: var(--muted);
            letter-spacing: 0.08em;
            margin-bottom: 8px;
        }

        .big {
            font-size: 2rem;
            font-weight: 700;
        }

        .replicas {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 8px;
        }

        .chip {
            background: #e3f2fd;
            border: 1px solid #b3e5fc;
            border-radius: 999px;
            padding: 6px 10px;
            font-weight: 700;
            font-size: 0.9rem;
        }

        .controls {
            margin-top: 16px;
            display: grid;
            gap: 12px;
        }

        .row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            align-items: center;
        }

        input {
            border: 2px solid #d7d3c8;
            border-radius: 10px;
            padding: 10px 12px;
            min-width: 95px;
            background: #fff;
            outline: none;
        }

        input:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 4px var(--ring);
        }

        button {
            border: none;
            border-radius: 10px;
            padding: 10px 14px;
            font-weight: 700;
            cursor: pointer;
            color: #fff;
            transition: transform 0.12s ease;
        }

        button:hover { transform: translateY(-1px); }

        .btn-main { background: var(--accent); }
        .btn-alt { background: var(--accent-2); }
        .btn-danger { background: var(--danger); }

        pre {
            margin: 8px 0 0;
            background: #091524;
            color: #c7f9cc;
            border-radius: 10px;
            padding: 12px;
            max-height: 220px;
            overflow: auto;
            font-size: 0.86rem;
        }

        @media (max-width: 540px) {
            .page { padding: 14px; }
            .row { flex-direction: column; align-items: stretch; }
            button, input { width: 100%; }
        }
    </style>
</head>
<body>
    <main class="page">
        <h1>Load Balancer Dashboard</h1>
       

        <section class="grid">
            <article class="card">
                <div class="label">Replica Count</div>
                <div id="replicaCount" class="big">-</div>
            </article>
            <article class="card">
                <div class="label">Last Routed Response</div>
                <div id="lastRouted">Not requested yet</div>
            </article>
        </section>

        <section class="card" style="margin-top: 14px;">
            <div class="label">Replicas</div>
            <div id="replicas" class="replicas"></div>

            <div class="controls">
                <div class="row">
                    <button class="btn-main" id="refreshBtn" type="button">Refresh /rep</button>
                    <button class="btn-alt" id="routeBtn" type="button">Send /home Request</button>
                </div>

                <div class="row">
                    <input id="addN" type="number" min="1" value="1" />
                    <input id="addHosts" type="text" placeholder="host1,host2 (optional)" />
                    <button class="btn-main" id="addBtn" type="button">Add Replicas</button>
                </div>

                <div class="row">
                    <input id="rmN" type="number" min="1" value="1" />
                    <input id="rmHosts" type="text" placeholder="host1,host2 (optional)" />
                    <button class="btn-danger" id="rmBtn" type="button">Remove Replicas</button>
                </div>
            </div>

            <pre id="output">Ready.</pre>
        </section>
    </main>

    <script>
        const replicaCount = document.getElementById("replicaCount");
        const replicasDiv = document.getElementById("replicas");
        const output = document.getElementById("output");
        const lastRouted = document.getElementById("lastRouted");

        function parseHostnames(raw) {
            return raw
                .split(",")
                .map((v) => v.trim())
                .filter((v) => v.length > 0);
        }

        function setOutput(obj) {
            output.textContent = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
        }

        function renderReplicas(list) {
            replicasDiv.innerHTML = "";
            if (!list || list.length === 0) {
                const empty = document.createElement("span");
                empty.textContent = "No replicas running";
                empty.style.color = "#7f8c8d";
                replicasDiv.appendChild(empty);
                return;
            }
            list.forEach((name) => {
                const chip = document.createElement("span");
                chip.className = "chip";
                chip.textContent = name;
                replicasDiv.appendChild(chip);
            });
        }

        async function refreshReplicas() {
            const res = await fetch("/rep");
            const data = await res.json();
            const msg = data.message || {};
            replicaCount.textContent = msg.N ?? 0;
            renderReplicas(msg.replicas || []);
            setOutput(data);
        }

        async function postJson(url, method, payload) {
            const res = await fetch(url, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            setOutput(data);
            await refreshReplicas();
        }

        document.getElementById("refreshBtn").addEventListener("click", refreshReplicas);

        document.getElementById("routeBtn").addEventListener("click", async () => {
            const res = await fetch("/home");
            const data = await res.json();
            lastRouted.textContent = data.message || JSON.stringify(data);
            setOutput(data);
        });

        document.getElementById("addBtn").addEventListener("click", async () => {
            const n = parseInt(document.getElementById("addN").value, 10);
            const hosts = parseHostnames(document.getElementById("addHosts").value);
            await postJson("/add", "POST", { n, hostnames: hosts });
        });

        document.getElementById("rmBtn").addEventListener("click", async () => {
            const n = parseInt(document.getElementById("rmN").value, 10);
            const hosts = parseHostnames(document.getElementById("rmHosts").value);
            await postJson("/rm", "DELETE", { n, hostnames: hosts });
        });

        refreshReplicas();
        setInterval(refreshReplicas, 5000);
    </script>
</body>
</html>
"""

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

@app.route("/", methods=["GET"])
def dashboard():
    return render_template_string(DASHBOARD_HTML)

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

        # FIX: the backend being reachable doesn't mean it has this route.
        # A 404 from the server means "<path> isn't registered" -> translate
        # to the spec's error format instead of proxying Flask's raw 404 page.
        if resp.status_code == 404:
            return jsonify({
                "message": f"<Error> '/{subpath}' endpoint does not exist in server replicas",
                "status": "failure"
            }), 400

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
    # FIX: threaded=True so the heartbeat monitor's /heartbeat polls and
    # concurrent client requests (e.g. the 10,000-request load tests) don't
    # queue behind each other on a single-threaded dev server.
    app.run(host="0.0.0.0", port=5000, threaded=True)