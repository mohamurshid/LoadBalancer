"""
A-1: Launch 10000 async requests on N=3 server containers,
report how many requests each server handled, in a bar chart.

Run this AFTER the load balancer stack is up (N=3 by default).
"""

import asyncio
import aiohttp
from collections import Counter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

LB_URL = "http://localhost:5000"
NUM_REQUESTS = 10000
CONCURRENCY = 200


async def send_request(http_session, semaphore):
    try:
        async with semaphore:
            async with http_session.get(f"{LB_URL}/home") as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                # message looks like "Hello from Server: <hostname>"
                server_name = data["message"].split(":")[-1].strip()
                return server_name
    except Exception:
        return None


async def run_load_test(num_requests):
    timeout = aiohttp.ClientTimeout(total=8)
    connector = aiohttp.TCPConnector(limit=CONCURRENCY, limit_per_host=CONCURRENCY)
    semaphore = asyncio.Semaphore(CONCURRENCY)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as http_session:
        tasks = [send_request(http_session, semaphore) for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)
    return results


def main():
    print(f"Sending {NUM_REQUESTS} async requests to {LB_URL} ...")
    results = asyncio.run(run_load_test(NUM_REQUESTS))

    counts = Counter(r for r in results if r is not None)
    failed = sum(1 for r in results if r is None)

    print("Request distribution:")
    for server, count in counts.items():
        print(f"  {server}: {count}")
    if failed:
        print(f"  Failed requests: {failed}")

    plt.figure(figsize=(8, 5))
    plt.bar(counts.keys(), counts.values(), color="steelblue")
    plt.xlabel("Server")
    plt.ylabel("Number of Requests Handled")
    plt.title(f"Request Distribution Across Servers (N=3, total={NUM_REQUESTS})")
    plt.subplots_adjust(left=0.12, right=0.98, top=0.9, bottom=0.2)
    plt.savefig("a1_request_distribution.png")
    print("Saved chart to a1_request_distribution.png")


if __name__ == "__main__":
    main()
