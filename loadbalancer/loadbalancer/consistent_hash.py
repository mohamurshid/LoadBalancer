"""
Consistent Hashing implementation for Task 2.

- #slots (M) = 512
- Virtual servers per physical server (K) = log2(512) = 9
- Request hash:        H(i) = i^2 + 2*i + 17          (mod M)
- Virtual server hash: Phi(i, j) = i^2 + j^2 + 2*j + 25 (mod M)

The hash map is implemented as a fixed-size array of size M.
Each slot is either empty (None) or holds a server hostname.
Collisions are resolved using linear probing.
"""

import math
import os

M_SLOTS = 512
K_VIRTUAL = int(math.log2(M_SLOTS))  # = 9


class ConsistentHashMap:
    def __init__(self, num_slots=M_SLOTS, k_virtual=K_VIRTUAL):
        self.num_slots = num_slots
        self.k_virtual = k_virtual
        # HASH_MODE controls which pair of hash functions is used:
        #   spec     -> assignment quadratic formulas
        #   modified -> multiplicative formulas used for A-4 comparison
        self.hash_mode = os.environ.get("HASH_MODE", "spec").strip().lower()
        # slot_array[slot] = hostname string, or None if empty
        self.slot_array = [None] * self.num_slots
        # quick lookup: hostname -> list of slot indices it occupies
        self.server_slots = {}

    # ---------- Hash functions ----------

    def request_hash(self, request_id: int) -> int:
        """Return request hash for either spec or modified mode."""
        if self.hash_mode == "modified":
            return (request_id * 2654435761) % self.num_slots
        return (request_id ** 2 + 2 * request_id + 17) % self.num_slots

    def virtual_server_hash(self, server_id: int, replica_id: int) -> int:
        """Return virtual server hash for either spec or modified mode."""
        if self.hash_mode == "modified":
            return ((server_id * 2654435761) ^ (replica_id * 40503)) % self.num_slots
        return (server_id ** 2 + replica_id ** 2 + 2 * replica_id + 25) % self.num_slots

    # ---------- Probing helper ----------

    def _find_free_slot(self, start_slot: int) -> int:
        """Linear probing: walk forward (wrapping around) until an empty slot is found."""
        slot = start_slot % self.num_slots
        for _ in range(self.num_slots):
            if self.slot_array[slot] is None:
                return slot
            slot = (slot + 1) % self.num_slots
        raise Exception("Consistent hash map is full — cannot place server")

    # ---------- Server management ----------

    def add_server(self, hostname: str, server_id: int):
        """Places K virtual replicas of this server into the hash map."""
        placed_slots = []
        for j in range(self.k_virtual):
            ideal_slot = self.virtual_server_hash(server_id, j)
            actual_slot = self._find_free_slot(ideal_slot)
            self.slot_array[actual_slot] = hostname
            placed_slots.append(actual_slot)
        self.server_slots[hostname] = placed_slots

    def remove_server(self, hostname: str):
        """Removes all virtual replicas belonging to this server."""
        slots = self.server_slots.pop(hostname, [])
        for slot in slots:
            self.slot_array[slot] = None

    # ---------- Request routing ----------

    def get_server_for_request(self, request_id: int):
        """
        Finds the slot for this request, then walks clockwise (forward)
        until it finds an occupied slot -> that server handles the request.
        """
        if not self.server_slots:
            return None

        slot = self.request_hash(request_id)
        for _ in range(self.num_slots):
            if self.slot_array[slot] is not None:
                return self.slot_array[slot]
            slot = (slot + 1) % self.num_slots
        return None  # should never happen if at least one server exists
