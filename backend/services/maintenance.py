"""Coordinate workspace replacement with API requests and background work."""
from threading import Lock

class WorkspaceGate:
    def __init__(self):
        self.lock = Lock()
        self.readers = 0
        self.exclusive = False
        self.update_pending = False

    def enter(self, exclusive=False):
        with self.lock:
            if self.exclusive or (exclusive and self.readers):
                return False
            if exclusive:
                self.exclusive = True
            else:
                self.readers += 1
            return True

    def leave(self, exclusive=False):
        with self.lock:
            if exclusive:
                self.exclusive = False
            else:
                self.readers -= 1

gate = WorkspaceGate()

def activity():
    from contextlib import closing
    from services.database import _connect
    from backend.services.jobs import jobs
    with jobs.lock:
        running = sum(item['status'] in {'queued', 'running'} for item in jobs.items.values())
    with closing(_connect()) as database:
        processing = database.execute("SELECT COUNT(*) FROM subject_processing_jobs WHERE status IN ('queued','running')").fetchone()[0]
        practice = database.execute("SELECT COUNT(*) FROM exam_sessions WHERE status IN ('created','preparing','answering','running')").fetchone()[0]
    return {'background_jobs': running + processing, 'practice_sessions': practice, 'safe': not (running or processing or practice)}
