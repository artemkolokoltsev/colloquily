"""PyInstaller entry point; only this process owns the loopback listener."""
import argparse
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir")
    parser.add_argument("--parent-stdin", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        import tempfile
        with tempfile.TemporaryDirectory(prefix="colloquily-frozen-check-") as data:
            os.environ["COLLOQUILY_DATA_DIR"] = data
            import backend
            from backend.self_test import run
            run()
        return
    if args.data_dir:
        os.environ["COLLOQUILY_DATA_DIR"] = args.data_dir
    import backend
    import uvicorn
    from backend.main import app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="info", timeout_graceful_shutdown=5))
    if args.parent_stdin:
        def watch_parent():
            sys.stdin.readline()  # shutdown command or EOF after parent exits
            server.should_exit = True
        threading.Thread(target=watch_parent, daemon=True).start()
    server.run()

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
