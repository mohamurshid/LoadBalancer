"""
Simple web server for Task 1.
Exposes:
  GET /home       -> identifies which server replica answered
  GET /heartbeat  -> used by the load balancer to check if this server is alive
"""

import os
from flask import Flask, jsonify

app = Flask(__name__)

# Server ID is passed in as an environment variable when the container starts
SERVER_ID = os.environ.get("SERVER_ID", "unknown")

