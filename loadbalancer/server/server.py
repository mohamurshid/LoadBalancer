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


@app.route("/home", methods=["GET"])
def home():
    response = {
        "message": f"Hello from Server: {SERVER_ID}",
        "status": "successful"
    }
    return jsonify(response), 200


@app.route("/heartbeat", methods=["GET"])
def heartbeat():
    # Empty body, just needs a valid response code to signal "I'm alive"
    return "", 200


if __name__ == "__main__":
    # Listen on all interfaces inside the container, port 5000
<<<<<<< HEAD
    app.run(host="0.0.0.0", port=5000, threaded=True)
=======
    app.run(host="0.0.0.0", port=5000, threaded=True)
>>>>>>> 5055b1d4263583c64c7937d1292f427679c487cf
