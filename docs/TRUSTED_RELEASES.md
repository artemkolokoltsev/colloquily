# Trusted desktop installers

Updater signatures authenticate update payloads. Apple Developer ID/notarization
and Windows Authenticode authenticate the OS publisher. One does not replace the
other. Do not describe a build as OS-trusted unless its native verification passed.

## Current account readiness

As checked on 2026-10-27, the maintainer has an Apple Developer membership, but
this Mac has **no valid code-signing identity**. GitHub has the updater key pair,
but none of the Apple or Windows publisher-signing secrets. Membership alone
cannot sign a distributable app.

The preview workflow now supports independent platform signing: Mac previews
can be Developer ID signed and notarized while Windows remains clearly labeled
OS-unsigned. Any partially configured signing credentials fail the build instead
of silently producing an unsigned installer. Stable releases still require both
platforms' production credentials.

## Enable Mac distribution signing

1. On the Mac used to manage signing, open **Keychain Access → Certificate
   Assistant → Request a Certificate From a Certificate Authority**. Enter your
   developer email/name and save the request to disk. This creates the associated
   private key in your keychain. Do not send that key in chat.
2. In [Apple Developer certificates](https://developer.apple.com/account/resources/certificates/list),
   create a **Developer ID Application** certificate using that request. For
   direct DMG downloads, do not select Apple Development, Apple Distribution or
   Developer ID Installer. The account holder may need to perform this step.
3. Download and install the certificate in the same Mac keychain. In **My
   Certificates**, it must expand to show its matching private key. Export the
   certificate and private key together as a password-protected `.p12` file.
4. In [repository Actions secrets](https://github.com/artemkolokoltsev/colloquily/settings/secrets/actions),
   configure the following. Never commit certificates, passwords, or private keys.

| Secret | Value |
| --- | --- |
| `APPLE_CERTIFICATE` | Base64-encoded contents of the exported `.p12` |
| `APPLE_CERTIFICATE_PASSWORD` | Password chosen for that `.p12` |
| `APPLE_SIGNING_IDENTITY` | Full identity, e.g. `Developer ID Application: Your Name (TEAMID)` |
| `APPLE_TEAM_ID` | Your Apple Developer team ID |
| `APPLE_ID` | Apple account email used for notarization |
| `APPLE_PASSWORD` | App-specific password generated for notarization; not the account password |

The existing `TAURI_SIGNING_PRIVATE_KEY` and `TAURI_UPDATER_PUBLIC_KEY` must stay
unchanged. The release workflow imports the Developer ID certificate before
building/signing the Python backend. Tauri signs and submits the app for Apple
notarization. Publication then requires all of:

- `codesign --verify --deep --strict` succeeds;
- the application carries Developer ID Application authority for the expected team;
- the notarization ticket validates with `xcrun stapler validate`;
- Gatekeeper reports `Notarized Developer ID` for the application bundle.

After adding these secrets, push a **new version tag**; existing published
installers do not gain trust retroactively. Never replace the published 0.1.6
assets with newly signed binaries under the same version.

Apple references: [Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates/),
[certificate requests](https://developer.apple.com/help/account/certificates/create-a-certificate-signing-request/),
and [Tauri signing/notarization](https://v2.tauri.app/distribute/sign/macos/).

## Windows

No Windows publisher-signing account/certificate has been supplied. The existing
workflow supports an exportable code-signing PFX through `WINDOWS_CERTIFICATE`
and `WINDOWS_CERTIFICATE_PASSWORD`, where the issuer permits this. Many modern
certificates use hardware or hosted signing and cannot be exported this way.
For those, configure Tauri's signing command for the chosen provider before
turning on Windows signing; Azure Artifact Signing requires its own account and
identity setup. See [Tauri's Windows signing documentation](https://v2.tauri.app/distribute/sign/windows/).

The verifier requires a valid Authenticode signature and timestamp. A signature
does not guarantee that every Windows machine will show no SmartScreen warning;
reputation and enterprise policies also apply. Do not instruct users to disable
Gatekeeper, SmartScreen, antivirus, or other security controls.

## Website trust labels

New builds publish `trust-<target>.json` files and include their records in
`downloads.json` under `native_trust`. Values come from native CI verification.
Use `os_signed: true` and, for Mac, `notarized: true` to display the corresponding
labels. An absent record means **unknown/unverified**, never trusted. Older
0.1.6 metadata has no native-trust records. Keep preview labels independent of
signing labels: a notarized preview is still a preview.

Describe privacy precisely: study content is processed locally; software updates
and model downloads contact their providers. Avoid claims such as “100% secure”
or “complete privacy.”
