"""Validate optional preview signing or required production signing, without logging secrets."""
import argparse
import os
import sys


def preflight(platform, environment, required=False):
    fields = {
        'macOS': ['APPLE_CERTIFICATE', 'APPLE_CERTIFICATE_PASSWORD', 'APPLE_SIGNING_IDENTITY', 'APPLE_ID', 'APPLE_PASSWORD', 'APPLE_TEAM_ID'],
        'Windows': ['WINDOWS_CERTIFICATE', 'WINDOWS_CERTIFICATE_PASSWORD'],
    }[platform]
    enabled = required or any(environment.get(name) for name in fields)
    missing = [name for name in fields if not environment.get(name)] if enabled else []
    if platform == 'macOS' and environment.get('APPLE_SIGNING_IDENTITY') and not environment['APPLE_SIGNING_IDENTITY'].startswith('Developer ID Application:'):
        raise ValueError('Use a Developer ID Application identity for direct Mac downloads, not an Apple Development identity.')
    if missing:
        raise ValueError('OS signing is partially configured. Add repository secrets: ' + ', '.join(missing))
    return enabled


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--required', action='store_true')
    args = parser.parse_args()
    try:
        enabled = preflight(os.environ['RUNNER_OS'], os.environ, args.required)
    except ValueError as error:
        sys.exit(str(error))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write(f'enabled={str(enabled).lower()}\n')
    print('OS signing is configured; native verification is required.' if enabled else 'Preview only: no OS signing credentials. Installer trust must not be advertised.')
