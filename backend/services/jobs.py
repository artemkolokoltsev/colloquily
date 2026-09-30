"""Bounded in-process tasks; ingestion retains its existing durable checkpoints."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Lock
from uuid import uuid4

class Jobs:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="colloquily")
        self.lock = Lock()
        self.items = {}
        self.keys = {}

    def get(self, key):
        with self.lock:
            return deepcopy(self.items.get(key))

    def latest(self, key):
        with self.lock:
            return deepcopy(self.items.get(self.keys.get(key)))

    def update(self, key, **values):
        with self.lock:
            self.items[key].update(values)

    def submit(self, key, message, work):
        with self.lock:
            previous = self.keys.get(key)
            if previous and self.items[previous]["status"] in {"queued", "running"}:
                return deepcopy(self.items[previous])
            ident = uuid4().hex
            self.items[ident] = {"id": ident, "status": "queued", "message": message}
            self.keys[key] = ident
        def run():
            self.update(ident, status="running")
            try:
                result = work(lambda **values: self.update(ident, **values))
                self.update(ident, status="completed", result=result)
            except Exception as exc:
                self.update(ident, status="failed", error=str(exc), message=str(exc))
        self.pool.submit(run)
        return self.get(ident)

jobs = Jobs()
