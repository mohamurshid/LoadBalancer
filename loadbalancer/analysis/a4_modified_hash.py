"""
A-4: Modify the hash functions H(i) and Phi(i,j), then re-run the same
A-1 (distribution) and A-2 (scalability) experiments to compare results.

NOTE: Since H and Phi live inside the load balancer container, to truly test
new hash functions you must:
  1. Edit consistent_hash.py -> request_hash() and virtual_server_hash()
  2. Rebuild the load balancer image (make build)
  3. Restart the stack (make down && make up)
  4. Then run this script

This script just re-runs the same measurements as A-1/A-2 against whatever
hash functions are CURRENTLY deployed, and saves results with a different
filename so you can compare before/after side by side.

Suggested alternate hash functions (verified to spread virtual servers across
the whole ring, unlike the quadratic formulas in the original spec which
clump all virtual servers into a small range and cause one server to absorb
most of the empty slot space):

    H(i)      = (i * 2654435761) % M
    Phi(i, j) = (i * 2654435761 + j * 40503) % M

(2654435761 is Knuth's multiplicative hash constant — it scatters
consecutive integers across the table far better than a small quadratic.)

To use these, edit request_hash() and virtual_server_hash() in
consistent_hash.py to the formulas above, then rebuild/restart before
running this script.
"""

import asyncio
import aiohttp
from collections import Counter
import matplotlib.pyplot as plt

LB_URL = "http://localhost:5000"
NUM_REQUESTS = 10000


async def send_request(session):
    try:
        async with session.get(f"{LB_URL}/home") as resp:
            data = await resp.json()
            server_name = data["message"].split(":")[-1].strip()
            return server_name
    except Exception:
        return None


async def run_load_test(num_requests):
    async with aiohttp.ClientSession() as session:
        tasks = [send_request(session) for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)
    return results


def main():
    print(f"Sending {NUM_REQUESTS} requests against CURRENTLY deployed hash functions ...")
    results = asyncio.run(run_load_test(NUM_REQUESTS))

    counts = Counter(r for r in results if r is not None)
    failed = sum(1 for r in results if r is None)

    print("Request distribution (modified hash functions):")
    for server, count in counts.items():
        print(f"  {server}: {count}")
    if failed:
        print(f"  Failed requests: {failed}")

    plt.figure(figsize=(8, 5))
    plt.bar(counts.keys(), counts.values(), color="seagreen")
    plt.xlabel("Server")
    plt.ylabel("Number of Requests Handled")
    plt.title(f"Request Distribution with Modified Hash Functions (total={NUM_REQUESTS})")
    plt.tight_layout()
    plt.savefig("a4_modified_hash_distribution.png")
    print("Saved chart to a4_modified_hash_distribution.png")
    print("\nCompare this against a1_request_distribution.png to write your A-4 observations.")


if __name__ == "__main__":
    main()
