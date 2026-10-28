"""Fail publication if a purportedly signed native build lacks platform trust."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def run(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError('Native trust verification failed: ' + command[0])
    return result.stdout + result.stderr


def verify(root, target, required):
    if target not in {'aarch64-apple-darwin', 'x86_64-apple-darwin', 'x86_64-pc-windows-msvc'}:
        raise ValueError('Unsupported native target')
    record = {'target': target, 'os_signed': False, 'notarized': False}
    if required and 'apple' in target:
        apps = list(root.glob('macos/*.app'))
        if len(apps) != 1:
            raise ValueError('Expected one application bundle to verify')
        app = str(apps[0])
        run(['/usr/bin/codesign', '--verify', '--deep', '--strict', app])
        identity = run(['/usr/bin/codesign', '-d', '--verbose=4', app])
        team = os.environ.get('APPLE_TEAM_ID')
        if 'Authority=Developer ID Application:' not in identity or not team or f'TeamIdentifier={team}\n' not in identity:
            raise ValueError('Application does not have the expected Developer ID signing identity')
        run(['/usr/bin/xcrun', 'stapler', 'validate', app])
        assessment = run(['/usr/sbin/spctl', '--assess', '--type', 'execute', '--verbose=2', app])
        if 'Notarized Developer ID' not in assessment:
            raise ValueError('Gatekeeper did not identify a notarized Developer ID application')
        record.update(os_signed=True, notarized=True)
    elif required and 'windows' in target:
        installers = list(root.glob('nsis/*.exe'))
        if len(installers) != 1:
            raise ValueError('Expected one NSIS installer to verify')
        env = dict(os.environ, COLLOQUILY_VERIFY_INSTALLER=str(installers[0].resolve()))
        result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command',
            "$s=Get-AuthenticodeSignature -LiteralPath $env:COLLOQUILY_VERIFY_INSTALLER; if ($s.Status -ne 'Valid' -or !$s.TimeStamperCertificate) { throw 'Installer signature or timestamp is invalid' }"], env=env, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise ValueError('Windows installer signature or timestamp verification failed')
        record['os_signed'] = True
    path = root/f'trust-{target}.json'
    path.write_text(json.dumps(record, indent=2)+'\n')
    print('Native trust evidence written: ' + path.name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('target')
    parser.add_argument('--required', action='store_true')
    args = parser.parse_args()
    verify(args.directory, args.target, args.required)
