"""
A-2: Increment N from 2 to 6, launch 10000 requests on each increment,
report the AVERAGE load per server at each N, as a line chart.

This script controls the load balancer via /add and /rm to change N between runs.
Run this AFTER the load balancer stack is up.
"""

import asyncio
import aiohttp
import requests
import subprocess
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

LB_URL = "http://localhost:5000"
NUM_REQUESTS = 10000
N_VALUES = [2, 3, 4, 5, 6]
CONCURRENCY = 200


session = requests.Session()
retry = Retry(
    total=2,
    connect=2,
    read=2,
    backoff_factor=0.2,
    status_forcelist=[502, 503, 504],
    allowed_methods=["GET", "POST", "DELETE"],
)
adapter = HTTPAdapter(max_retries=retry, pool_connections=32, pool_maxsize=64)
session.mount("http://", adapter)


async def send_request(http_session, semaphore):
    try:
        async with semaphore:
            async with http_session.get(f"{LB_URL}/home") as resp:
                if resp.status == 200:
                    await resp.json()
                    return True
                return False
    except Exception:
        return False


async def run_load_test(num_requests):
    timeout = aiohttp.ClientTimeout(total=8)
    connector = aiohttp.TCPConnector(limit=CONCURRENCY, limit_per_host=CONCURRENCY)
    semaphore = asyncio.Semaphore(CONCURRENCY)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as http_session:
        tasks = [send_request(http_session, semaphore) for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)
    return results


def get_current_n():
    resp = session.get(f"{LB_URL}/rep", timeout=3)
    return resp.json()["message"]["N"]


def get_replicas():
    resp = session.get(f"{LB_URL}/rep", timeout=3)
    return list(resp.json()["message"]["replicas"])


def get_container_ip(container_name):
    """Return container IP address using docker inspect, or None on failure."""
    try:
        cmd = [
            "docker",
            "inspect",
            "-f",
            "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            container_name,
        ]
        out = subprocess.check_output(cmd, text=True).strip()
        return out or None
    except Exception:
        return None


def wait_for_replicas_ready(replicas, timeout_seconds=60):
    """
    Poll each replica's /heartbeat until all respond 200 or timeout expires.
    Returns True if all replicas become healthy; False otherwise.
    """
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        all_ready = True
        for replica in replicas:
            ip = get_container_ip(replica)
            if not ip:
                all_ready = False
                continue

            try:
                resp = session.get(f"http://{ip}:5000/heartbeat", timeout=1.5)
                if resp.status_code != 200:
                    all_ready = False
            except requests.exceptions.RequestException:
                all_ready = False

        if all_ready:
            return True

        time.sleep(1)

    return False


def wait_for_n(target_n, timeout_seconds=30):
    """Wait until /rep reports target N, or return False on timeout."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if get_current_n() == target_n:
            return True
        time.sleep(0.5)
    return False


def set_n(target_n):
    before = set(get_replicas())
    current_n = get_current_n()
    if target_n > current_n:
        session.post(
            f"{LB_URL}/add",
            json={"n": target_n - current_n, "hostnames": []},
            timeout=8,
        )
    elif target_n < current_n:
        session.delete(
            f"{LB_URL}/rm",
            json={"n": current_n - target_n, "hostnames": []},
            timeout=8,
        )

    if not wait_for_n(target_n):
        print(f"WARNING: Timed out waiting for N={target_n} in /rep")

    after = set(get_replicas())
    added = sorted(list(after - before))
    return added


def main():
    avg_loads = []

    for n in N_VALUES:
        print(f"\nSetting N = {n} ...")
        added_replicas = set_n(n)

        if added_replicas:
            print(f"Warm-up: waiting for {len(added_replicas)} new replica(s) to pass /heartbeat ...")
            ready = wait_for_replicas_ready(added_replicas, timeout_seconds=90)
            if not ready:
                print("WARNING: Not all new replicas became ready before timeout.")

        print(f"Sending {NUM_REQUESTS} requests ...")
        results = asyncio.run(run_load_test(NUM_REQUESTS))
        successful = sum(1 for r in results if r)
        errors = NUM_REQUESTS - successful

        avg_load = successful / n
        avg_loads.append(avg_load)
        expected = NUM_REQUESTS / n
        print(
            f"N={n}: success_count={successful}, error_count={errors}, "
            f"expected_avg={expected:.1f}, observed_avg={avg_load:.1f}"
        )
        # Give local sockets a brief cool-down between scale rounds on Windows.
        time.sleep(1)

    plt.figure(figsize=(8, 5))
    plt.plot(N_VALUES, avg_loads, marker="o", color="darkorange")
    plt.xlabel("Number of Servers (N)")
    plt.ylabel("Average Requests Handled per Server")
    plt.title(f"Average Server Load vs N (total requests={NUM_REQUESTS} each run)")
    plt.grid(True)
    plt.subplots_adjust(left=0.12, right=0.98, top=0.9, bottom=0.12)
    plt.savefig("a2_avg_load_vs_n.png")
    print("\nSaved chart to a2_avg_load_vs_n.png")


if __name__ == "__main__":
    main()
