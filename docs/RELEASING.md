# Releasing the desktop app

The release pipeline is split in two on purpose:

1. **GitHub Actions** (`.github/workflows/release-desktop.yml`) builds
   **unsigned** DMG / MSI / AppImage bundles on every `v*` tag and uploads
   them as a draft GitHub release.
2. **A maintainer** then signs / notarizes each artifact on their own
   machine using the credentials below, replaces the unsigned files in the
   draft release with the signed ones, and publishes.

Why split: signing certs and notarization API keys are credentials we don't
want sitting in GitHub Actions secrets while the project is still pre-1.0.
When the project is ready for fully-automated releases, the steps below
should move into a separate `release-sign.yml` gated on protected
environment secrets.

## Tag → draft release

```sh
git tag v0.1.0
git push --tags
# Wait for release-desktop.yml to finish. A draft release titled `v0.1.0`
# now exists with three unsigned bundles attached.
gh release download v0.1.0 --pattern '*'    # or download from the web UI
```

## macOS — Developer ID signing + notarization

Prereqs (one-time):

- Apple Developer Program enrollment (\$99 / year).
- A **Developer ID Application** certificate in your local Keychain
  (Apple Developer portal → Certificates → Developer ID Application).
- An app-specific password for your Apple ID (appleid.apple.com → Sign-In
  and Security → App-Specific Passwords) — required for `notarytool`.

```sh
APPLE_ID="you@example.com"
APPLE_TEAM_ID="ABCDE12345"
APPLE_PASSWORD="abcd-efgh-ijkl-mnop"   # the app-specific password
SIGNING_IDENTITY="Developer ID Application: Your Name (ABCDE12345)"

# 1. Sign the .dmg's inner .app bundle (Tauri's DMG wraps a real .app).
hdiutil attach delete-me_0.1.0_aarch64.dmg
cp -R /Volumes/delete-me/delete-me.app /tmp/
hdiutil detach /Volumes/delete-me

codesign \
  --force --options runtime --timestamp \
  --sign "$SIGNING_IDENTITY" \
  --entitlements tauri-app/src-tauri/Entitlements.plist \
  --deep /tmp/delete-me.app

# 2. Re-bundle the signed .app into a new DMG.
hdiutil create -volname delete-me -srcfolder /tmp/delete-me.app \
  -ov -format UDZO delete-me_0.1.0_aarch64_signed.dmg
codesign --force --sign "$SIGNING_IDENTITY" --timestamp delete-me_0.1.0_aarch64_signed.dmg

# 3. Notarize.
xcrun notarytool submit delete-me_0.1.0_aarch64_signed.dmg \
  --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" --password "$APPLE_PASSWORD" \
  --wait

# 4. Staple the notarization ticket onto the DMG so it works offline.
xcrun stapler staple delete-me_0.1.0_aarch64_signed.dmg
```

If you don't already have one, drop a minimal `Entitlements.plist` at
`tauri-app/src-tauri/Entitlements.plist` granting the hardened-runtime
exceptions Tauri needs (network client, JIT for the WebView). Tauri's docs
list the canonical entries.

## Windows — Authenticode signing

Prereqs:

- An **EV code-signing certificate** on a hardware token (SmartScreen
  immediately trusts EV certs; non-EV certs require a reputation-building
  period that practically blocks fresh-install users).
- `signtool.exe` (ships with Windows SDK).

```cmd
signtool sign /n "Your Name" /tr http://timestamp.digicert.com /td sha256 ^
  /fd sha256 /a delete-me_0.1.0_x64_en-US.msi

signtool verify /pa /v delete-me_0.1.0_x64_en-US.msi
```

Hardware-token PINs cannot be scripted into CI without violating the EV
issuance terms — this is exactly why this step stays manual.

## Linux — AppImage signing (optional)

AppImage signing is not strictly required (no equivalent of Gatekeeper /
SmartScreen), but a signed AppImage lets users verify provenance:

```sh
gpg --detach-sign --armor delete-me_0.1.0_amd64.AppImage
# Upload both the .AppImage and the .AppImage.asc to the release.
```

Publish your signing key fingerprint in `docs/SECURITY.md` so users can
verify against a known source.

## Final step

1. In the draft GitHub Release, **delete** the unsigned files.
2. **Upload** the signed-and-notarized versions.
3. Update the release notes (changelog, signing fingerprint, install steps).
4. Click **Publish release**.
