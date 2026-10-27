# Permanent website download links

Use these links directly in website buttons. They do not contain a version and
will not need changing for each release. The `latest` tag is a rolling download
channel, including release candidates; it is not a stable-release endorsement.

| Platform | Permanent URL |
| --- | --- |
| macOS Apple Silicon (M1 and later) | https://github.com/artemkolokoltsev/colloquily/releases/download/latest/Colloquily-macos-arm64.dmg |
| macOS Intel | https://github.com/artemkolokoltsev/colloquily/releases/download/latest/Colloquily-macos-x64.dmg |
| Windows x64 | https://github.com/artemkolokoltsev/colloquily/releases/download/latest/Colloquily-windows-x64.exe |
| Download page | https://github.com/artemkolokoltsev/colloquily/releases/tag/latest |
| Version/platform metadata | https://github.com/artemkolokoltsev/colloquily/releases/download/latest/downloads.json |
| Checksums | https://github.com/artemkolokoltsev/colloquily/releases/download/latest/SHA256SUMS.txt |

```html
<a href="https://github.com/artemkolokoltsev/colloquily/releases/download/latest/Colloquily-macos-arm64.dmg">Download for Mac · Apple Silicon</a>
<a href="https://github.com/artemkolokoltsev/colloquily/releases/download/latest/Colloquily-macos-x64.dmg">Download for Mac · Intel</a>
<a href="https://github.com/artemkolokoltsev/colloquily/releases/download/latest/Colloquily-windows-x64.exe">Download for Windows · x64</a>
```

Ordinary links work without JavaScript, GitHub credentials or CORS. Do not copy
GitHub's temporary redirect URL from `release-assets.githubusercontent.com`.
Fetch `downloads.json` on your website's server/build process if you want to show
the version; browser cross-origin fetch support is not assumed. Avoid caching
this metadata indefinitely. The app's update feed is **latest.json**, not
**downloads.json**:

`https://github.com/artemkolokoltsev/colloquily/releases/download/latest/latest.json`

The download channel currently serves **v0.1.6-rc.1**, including its signed update
feed. Versions through 0.1.5 contain a placeholder trust key and need one manual
upgrade. The 0.1.7 update adds optional native publisher signing and verified trust
metadata; it is separate from the already-published 0.1.6 release.

## Publishing and recovery

Pushing `v0.1.7-rc.1` triggers the three-platform preview workflow. Once native
builds, browser checks and learning acceptance pass, it publishes immutable
version assets, the signed-update manifest, notices and checksums, then promotes
the website channel. Update signatures are separate from Apple notarization and
Windows Authenticode; previews retain OS installation warnings.

`publish_channel.py` verifies installer checksums and required platform payloads,
rejects older releases, copies fixed-name installers, and publishes the update
manifest last. Its feed always refers to immutable **version-tagged** payloads.
Copies to the rolling tag are not atomic: a link may briefly return 404 during
replacement. The app retries failed checks; an already-downloaded update remains
bound to its version's signature. Keep versioned release assets intact.

The `Refresh permanent download links` workflow can be run manually with an
already-published version tag to retry a failed promotion without rebuilding.
Merge this workflow onto the default branch to enable its manual and
`release.published` triggers. Preview publication calls the promoter directly,
so it works from the release branch. Signed stable releases remain drafts until
you publish them; publish only after the finalize-draft job succeeds.

All promotions share a GitHub Actions concurrency group. Do not run competing
manual promotions from a local terminal. Never replace an existing version tag
or delete its update payloads. A new binary needs a higher application version:
0.1.6 RC tags share application version 0.1.6, so a later automatic update must
bump the application version, not only the RC suffix.

## Updater key custody

The public trust key is committed in `src-tauri/tauri.conf.json`. The matching
private key is encrypted as GitHub Actions secret `TAURI_SIGNING_PRIVATE_KEY`;
`TAURI_UPDATER_PUBLIC_KEY` must match the committed public key. Keep these keys
for future releases. Changing the key strands installed apps.

A local recovery copy is in ignored `data/update-signing/colloquily.key` (0600,
inside a 0700 directory). Keep a secure backup outside this checkout before
removing local data. It is not included in the app or committed to Git. The key
has no passphrase; GitHub encrypts the secret at rest and the local copy relies
on filesystem protection. Never upload it as a release asset.

Native publisher-signing setup and website trust labels: [TRUSTED_RELEASES.md](TRUSTED_RELEASES.md).
