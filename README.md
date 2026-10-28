# iOS Builds

Public, central GitHub Actions build infrastructure for personal iPhone apps.
The source stays in its own repository; this repository selects a reviewed app,
checks out an immutable source commit and builds on a GitHub-hosted macOS runner.
No Mac is needed on your desk.

## Status

- First app: **OpenWhispr**, including its keyboard and Live Activity extensions.
- Manually dispatched **unsigned**, **Ad Hoc** and **TestFlight** paths implemented.
- Build and signing run on **separate ephemeral runners**. Source installation and
  build hooks do not receive Apple signing credentials.
- **Archives, IPAs and signing diagnostics are age-encrypted before upload.**
  Only the public recipient exists on the build runner. Decryption requires the
  local identity or the identity in a protected signing environment.
- **Public source repositories only.** Build logs and provenance are public.
- Default source is a reviewed, pinned commit; a branch/tag/commit override is
  resolved to its exact SHA before checkout and recorded with Xcode version.
- Config/profile validation tests and workflow linting run on Linux.
- **Not yet validated with a real macOS build or Apple credentials.** The first
  device build may expose upstream/toolchain issues. No paid macOS build is
  triggered by a push. Signing is disabled until explicitly enabled.

This uses Xcode directly, **not EAS Build**. No Expo cloud account is required.
An unsigned archive is NOT installable. A valid App Store Connect API key alone
is NOT a signing identity: a certificate/private key and profiles are also needed.

## First build

Configure artifact encryption first: **[docs/ARTIFACT-ENCRYPTION.md](docs/ARTIFACT-ENCRYPTION.md)**.
Then, from this directory (GitHub CLI authenticated):

```sh
# Uses the source commit pinned in apps/openwhispr.json.
gh workflow run build-ios.yml -f app=openwhispr -f distribution=unsigned
gh run list --workflow build-ios.yml
gh run watch RUN_ID
```

Standard GitHub-hosted runners in a public repository are generally free,
including the standard `macos-26` runner used here. Larger runners and external
services have separate pricing. GitHub usage policies and concurrency limits
still apply. The workflow has 90/30-minute build/sign timeouts.

To deliberately test another version:

```sh
gh workflow run build-ios.yml -f app=openwhispr -f source_ref=main -f distribution=unsigned
```

Review the resolved source SHA before approving signing. The public build manifest
records source repository, SHA, control-workflow SHA, run ID and Xcode version.
Build output is visible in public Actions logs. Signing/upload diagnostics are
captured separately and published only as encrypted artifacts.

## Set up signing

See **[docs/APPLE-SETUP.md](docs/APPLE-SETUP.md)** for Apple identifiers, App Groups,
certificates, profiles, secrets and TestFlight setup. Do not put keys in Git,
workflow inputs, chat messages or EXPO_PUBLIC variables.

Environments are **per app and distribution**:

- `ios-openwhispr-ad-hoc`
- `ios-openwhispr-testflight`

Repository variables:

| Variable | Purpose |
| --- | --- |
| `ARTIFACT_AGE_RECIPIENT` | Public age recipient; required even for unsigned builds |
| `APPLE_TEAM_ID` | Your 10-character Apple Developer team ID (visible in logs/config) |
| `IOS_SIGNING_ENABLED` | Must be exactly `true` to request a signed build; initially `false` |
| `XCODE_PATH` | Optional installed Xcode app path, e.g. `/Applications/Xcode_26.2.app` |

Both macOS jobs use `macos-26` and verify Xcode >=26.2. Without `XCODE_PATH`, the
runner's default Xcode is used and logged. Pin an available Xcode version when
reproducibility matters; runner image contents change over time.

### Ad Hoc: install over Tailscale

After signing setup:

```sh
gh workflow run build-ios.yml -f app=openwhispr -f distribution=ad-hoc
gh run list --workflow build-ios.yml
gh run watch RUN_ID
gh run download RUN_ID --pattern 'openwhispr-ad-hoc-*' --dir downloads
find downloads -name '*.ipa.age'
# If age is not on PATH, use the local tool path in docs/ARTIFACT-ENCRYPTION.md.
age --decrypt --identity ~/.local/share/ios-build-signing/artifacts.agekey \
  --output downloads/OpenWhispr.ipa /path/to/downloaded/OpenWhispr.ipa.age
~/dev/apple-dev-setup/iphone-wifi install "$PWD/downloads/OpenWhispr.ipa"
~/dev/apple-dev-setup/iphone-wifi launch com.bearylabs.openwhispr
```

The iPhone must be registered and included in all three Ad Hoc profiles. Developer
Mode and the existing device pairing are required. Signature/profile validity is
finite, but paid development does not use the free seven-day Personal Team limit.

### TestFlight

```sh
gh workflow run build-ios.yml -f app=openwhispr -f distribution=testflight
```

The workflow uploads to App Store Connect; processing and any export-compliance
questions still happen at Apple. Configure internal testers there. External
TestFlight testing can require beta review. Upload success is not a guarantee of
Apple processing success or immediate tester availability.

Artifacts expire after **7 days** and are publicly downloadable as ciphertext.
Signed IPAs contain Apple's embedded profiles (including device information for
Ad Hoc); decrypt only locally and keep the resulting IPA private. TestFlight
uploads use the plaintext IPA only on the ephemeral signing runner.

## OpenWhispr identity and feature scope

The disposable source checkout is wrapped with personal configuration:

- Main app: `com.bearylabs.openwhispr`
- Keyboard: `com.bearylabs.openwhispr.keyboard`
- Live Activity: `com.bearylabs.openwhispr.activity`
- App Group: `group.com.bearylabs.openwhispr`
- App and keyboard display name: `OpenWhispr` (matches upstream onboarding)
- URL scheme: `bearylabs-openwhispr`

Change the reviewed manifest before creating Apple identifiers if you prefer a
different identity. The upstream team ID/Expo owner/EAS project are removed and
upstream OTA updates are disabled, so this personal build does not consume the
maintainers' over-the-air releases. The upstream repository is not modified.

No extensions are removed. Release builds embed JavaScript and run without Metro.
However, compiling all features is not the same as provisioning all third-party
services: Apple sign-in/backend callbacks, Google OAuth, subscriptions, push,
Sentry and other hosted integrations may need configuration for your bundle ID
or cooperation from the service owner. Personal provider keys are entered in the
app, not CI. Paid Apple membership does not grant OpenWhispr Pro or private brand
assets. Missing licensed brand fonts use upstream's fallback.

## Add another app

1. Add a reviewed `apps/<name>.json` manifest based on the first app.
2. Add the app name to the `workflow_dispatch` choices in `build-ios.yml`.
3. Create its Apple identifiers, profiles and `ios-<app>-<distribution>` environments.
4. Add tests and validate the build before enabling signing.

Currently implemented: the **Expo adapter** for CommonJS `app.config.js` projects
with a Gemfile, one generated Xcode workspace and an explicitly named scheme.
OpenWhispr-specific environment overrides live in `prepare-expo.cjs`. Another
Expo project may need a reviewed preparation hook for its extensions/services.
Native Swift/Xcode and Flutter adapters are intentionally **not implemented yet**;
add an adapter once, rather than copy an entire workflow per app.

**Private source repositories are rejected**, even if a future token could read
them: compiler/package-manager output can expose source in public logs. Use a
separate private build-control repository for private apps. Do not add private
source credentials here. Manifests remain the source-repository allowlist.

## Local validation

```sh
# age and age-keygen must be on PATH to run encryption round-trip tests.
python3 -m unittest discover -s tests -v
node --check scripts/prepare-expo.cjs
for script in scripts/*.sh; do bash -n "$script"; done
# If Go is installed:
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.11
```

The validation workflow does not invoke macOS runners or access signing secrets.
See [docs/SECURITY.md](docs/SECURITY.md) for trust boundaries and limitations.
