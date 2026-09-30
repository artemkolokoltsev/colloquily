"""Check the real frozen server and parent-stdin lifecycle using disposable data."""
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def smoke(binary):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='colloquily-sidecar-smoke-') as folder:
        token = secrets.token_urlsafe(32)
        with tempfile.TemporaryFile(mode='w+b') as log:
            process = subprocess.Popen([str(Path(binary).resolve()), '--port', str(port),
                '--data-dir', folder, '--parent-stdin'], stdin=subprocess.PIPE,
                stdout=log, stderr=subprocess.STDOUT,
                env={**os.environ, 'COLLOQUILY_API_TOKEN': token})
            try:
                base = f'http://127.0.0.1:{port}'
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        log.seek(0)
                        raise RuntimeError(log.read().decode(errors='replace'))
                    try:
                        with urlopen(base + '/api/health', timeout=1) as response:
                            assert response.status == 200
                        break
                    except (URLError, TimeoutError):
                        time.sleep(.25)
                else:
                    raise RuntimeError('Frozen backend did not become ready within 120 seconds')
                for headers, expected in [({}, 401),
                    ({'X-Colloquily-Token': token, 'Origin': 'https://foreign.example'}, 403),
                    ({'X-Colloquily-Token': token}, 200)]:
                    try:
                        with urlopen(Request(base + '/api/exams', headers=headers), timeout=5) as response:
                            status = response.status
                    except HTTPError as exc:
                        status = exc.code
                    assert status == expected, (status, expected)
                # EOF is how an unexpected parent exit requests a clean shutdown.
                process.stdin.close()
                process.wait(timeout=10)
                assert process.returncode == 0, process.returncode
                print('Sidecar lifecycle passed: loopback health, token/origin checks, parent EOF shutdown.')
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)

if __name__ == '__main__':
    smoke(sys.argv[1])
