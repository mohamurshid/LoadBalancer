"""
A-3: Test all load balancer endpoints, and demonstrate that on server failure,
the load balancer detects it (via heartbeat) and spawns a replacement quickly.

Run this AFTER the load balancer stack is up.
"""

import time
import requests
import subprocess

LB_URL = "http://localhost:5000"


def test_rep():
    print("\n--- Testing GET /rep ---")
    resp = requests.get(f"{LB_URL}/rep")
    print(resp.status_code, resp.json())


def test_add():
    print("\n--- Testing POST /add ---")
    payload = {"n": 2, "hostnames": ["S_test1", "S_test2"]}
    resp = requests.post(f"{LB_URL}/add", json=payload)
    print(resp.status_code, resp.json())


def test_rm():
    print("\n--- Testing DELETE /rm ---")
    payload = {"n": 1, "hostnames": ["S_test1"]}
    resp = requests.delete(f"{LB_URL}/rm", json=payload)
    print(resp.status_code, resp.json())


def test_home_route():
    print("\n--- Testing GET /home (routed through load balancer) ---")
    resp = requests.get(f"{LB_URL}/home")
    print(resp.status_code, resp.json())


def test_invalid_route():
    print("\n--- Testing GET /other (should fail, endpoint doesn't exist on servers) ---")
    resp = requests.get(f"{LB_URL}/other")
    print(resp.status_code, resp.json())


def test_failure_recovery():
    print("\n--- Testing failure recovery ---")
    before = requests.get(f"{LB_URL}/rep").json()["message"]["replicas"]
    print("Replicas before failure:", before)

    victim = before[0]
    print(f"Killing container '{victim}' to simulate failure ...")
    subprocess.run(["docker", "kill", victim])

    print("Waiting for the load balancer to detect failure and respawn (~10s) ...")
    time.sleep(10)

    after = requests.get(f"{LB_URL}/rep").json()["message"]["replicas"]
    print("Replicas after recovery:", after)

    if len(after) == len(before) and victim not in after:
        print("Recovery successful: failed server was replaced, N is maintained.")
    else:
        print("Recovery did not complete as expected — check timing/logs.")


if __name__ == "__main__":
    test_rep()
    test_add()
    test_rm()
    test_home_route()
    test_invalid_route()
    test_failure_recovery()
