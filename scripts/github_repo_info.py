"""Update only this project's About metadata using existing Git credentials.

Credentials stay in memory; never print, persist, or accept secrets on the CLI.
"""
import json
import os
import subprocess
import urllib.error
import urllib.request

REPO = 'artemkolokoltsev/colloquily'

def main():
    result = subprocess.run(['git', 'credential', 'fill'],
        input=f'protocol=https\nhost=github.com\npath={REPO}.git\n\n',
        text=True, capture_output=True, env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'}, check=False)
    credential = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    token = credential.get('password')
    if result.returncode or not token:
        raise SystemExit('Existing GitHub credential is unavailable; no metadata changed.')
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'Colloquily-release-preparation',
        'Content-Type': 'application/json'}
    requests = [('', 'PATCH', {'description': 'Local-first oral exam preparation with source-grounded questions, local AI, and English/German support.',
        'homepage': f'https://github.com/{REPO}#readme'}),
        ('/topics', 'PUT', {'names': ['oral-exams', 'exam-preparation', 'local-first', 'local-ai', 'ollama', 'rag', 'tauri', 'react', 'fastapi', 'pdf', 'education']})]
    for suffix, method, payload in requests:
        request = urllib.request.Request(f'https://api.github.com/repos/{REPO}{suffix}',
            data=json.dumps(payload).encode(), headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response.read()
        except urllib.error.HTTPError as error:
            raise SystemExit(f'GitHub metadata update refused (HTTP {error.code}); no credentials were displayed.')
    print('GitHub description, homepage and topics updated.')

if __name__ == '__main__':
    main()
