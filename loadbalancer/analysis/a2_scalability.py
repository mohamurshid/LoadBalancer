"""
A-2: Increment N from 2 to 6, launch 10000 requests on each increment,
report the AVERAGE load per server at each N, as a line chart.

This script controls the load balancer via /add and /rm to change N between runs.
Run this AFTER the load balancer stack is up.
"""

import asyncio
import aiohttp
import requests
import matplotlib.pyplot as plt

LB_URL = "http://localhost:5000"
NUM_REQUESTS = 10000
N_VALUES = [2, 3, 4, 5, 6]


async def send_request(session):
    try:
        async with session.get(f"{LB_URL}/home") as resp:
            await resp.json()
            return True
    except Exception:
        return False


async def run_load_test(num_requests):
    async with aiohttp.ClientSession() as session:
        tasks = [send_request(session) for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)
    return results


def get_current_n():
    resp = requests.get(f"{LB_URL}/rep")
    return resp.json()["message"]["N"]


def set_n(target_n):
    current_n = get_current_n()
    if target_n > current_n:
        requests.post(f"{LB_URL}/add", json={"n": target_n - current_n, "hostnames": []})
    elif target_n < current_n:
        requests.delete(f"{LB_URL}/rm", json={"n": current_n - target_n, "hostnames": []})


def main():
    avg_loads = []

    for n in N_VALUES:
        print(f"\nSetting N = {n} ...")
        set_n(n)

        print(f"Sending {NUM_REQUESTS} requests ...")
        results = asyncio.run(run_load_test(NUM_REQUESTS))
        successful = sum(1 for r in results if r)

        avg_load = successful / n
        avg_loads.append(avg_load)
        print(f"N={n}: successful={successful}, avg load per server={avg_load:.1f}")

    plt.figure(figsize=(8, 5))
    plt.plot(N_VALUES, avg_loads, marker="o", color="darkorange")
    plt.xlabel("Number of Servers (N)")
    plt.ylabel("Average Requests Handled per Server")
    plt.title(f"Average Server Load vs N (total requests={NUM_REQUESTS} each run)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("a2_avg_load_vs_n.png")
    print("\nSaved chart to a2_avg_load_vs_n.png")


if __name__ == "__main__":
    main()
