# Apple setup (no local Mac required)

## 1. Team, app identifiers and capabilities

Wait for Developer Program enrollment to be active. Find the **Team ID** under
Apple Developer > Membership (not the App Store Connect issuer ID).

In Certificates, Identifiers & Profiles, create explicit identifiers matching
`apps/openwhispr.json`:

| Target | Bundle ID |
| --- | --- |
| App | `com.bearylabs.openwhispr` |
| Keyboard | `com.bearylabs.openwhispr.keyboard` |
| Live Activity | `com.bearylabs.openwhispr.activity` |

Register App Group `group.com.bearylabs.openwhispr`, enable App Groups for all
three identifiers and assign that group to each. The app also uses Sign in with
Apple; enable it on the main App ID if the generated entitlements require it.
Enable any additional capabilities requested by the actual generated build.

Do not use the upstream maintainer's identifiers or team. A custom bundle ID can
require separate backend/OAuth configuration; see the README feature-scope note.

## 2. Distribution certificate/private key

The initial foundation uses **manual signing** with an Apple Distribution
certificate and uploaded provisioning profiles. It does not yet automatically
create/rotate them through the Apple API. Everything here can be prepared with
Linux OpenSSL and Apple's web portal.

Work outside this Git repository in a private directory:

```sh
mkdir -p ~/.local/share/ios-build-signing
chmod 700 ~/.local/share/ios-build-signing
cd ~/.local/share/ios-build-signing
umask 077
openssl req -new -newkey rsa:2048 -nodes \
  -keyout distribution.key -out distribution.csr \
  -subj '/CN=Personal iOS Distribution'
```

Create an **Apple Distribution** certificate in the developer portal using that
CSR. Download it as `distribution.cer`, then:

```sh
openssl x509 -inform DER -in distribution.cer -out distribution.pem
openssl pkcs12 -export -inkey distribution.key -in distribution.pem \
  -out distribution.p12
```

Choose a strong, nonempty export password when prompted. Back up the private key
and P12 securely. Do not revoke or replace unrelated certificates; Apple's
certificate counts are limited.

## 3. Provisioning profiles

For **Ad Hoc**:

1. Register your iPhone's UDID in the Developer portal. The existing local pairing
   tools can inspect the identifier; do not confuse it with a serial number.
2. Create **Ad Hoc distribution** profiles for each of the three App IDs.
3. Select the Apple Distribution certificate created above and your iPhone in each.
4. Download all three `.mobileprovision` files.

For **TestFlight**, create three **App Store Connect distribution** profiles
instead. These do not contain device UDIDs. Use the same valid distribution
certificate if desired. Regenerate profiles after capability/certificate changes.

Create separate ZIPs per app/distribution, containing exactly the three profiles:

```sh
zip openwhispr-ad-hoc-profiles.zip ad-hoc/*.mobileprovision
zip openwhispr-testflight-profiles.zip testflight/*.mobileprovision
```

The workflow checks team, expiration, explicit App IDs, expected target set,
App Group and distribution type before export. Apple/Xcode additionally verify
certificate/profile compatibility and entitlements during signing/export.

## 4. GitHub environments and variables

Run these from `~/dev/ios-builds` after repository creation:

```sh
gh variable set APPLE_TEAM_ID --body YOURTEAMID
gh variable set IOS_SIGNING_ENABLED --body false
```

Environments `ios-openwhispr-ad-hoc` and `ios-openwhispr-testflight` are created as
part of initial repository setup. In GitHub > Settings > Environments:

- Restrict deployment branches to `main`.
- Add required reviewers **where your GitHub plan supports them**. Private-repo
  environment protections vary by plan; an environment name alone is not an
  approval gate. Without reviewers, only trusted maintainers should have write
  access and signing remains an explicit manual dispatch.

Install secrets using the CLI. The base64 examples below use Linux coreutils:

```sh
base64 -w0 ~/.local/share/ios-build-signing/distribution.p12 | \
  gh secret set IOS_CERTIFICATE_P12_BASE64 --env ios-openwhispr-ad-hoc
# This prompts; do not put the password directly on a command line.
gh secret set IOS_CERTIFICATE_PASSWORD --env ios-openwhispr-ad-hoc
base64 -w0 ~/.local/share/ios-build-signing/openwhispr-ad-hoc-profiles.zip | \
  gh secret set IOS_PROFILES_ZIP_BASE64 --env ios-openwhispr-ad-hoc
```

Repeat for `ios-openwhispr-testflight`, using the **TestFlight profiles ZIP**.
Certificate and password can be the same. Profile ZIPs must contain no other apps,
no source files and no private keys. Base64 is encoding, not encryption: treat it
as the underlying secret.

Only after setup/review:

```sh
gh variable set IOS_SIGNING_ENABLED --body true
```

## 5. App Store Connect API key (TestFlight upload)

Create a **team API key** with App Manager access in App Store Connect > Users and
Access > Integrations. This foundation uses it for upload only; it does not
require it for an Ad Hoc build. Record Key ID and Issuer ID, and save the `.p8`
file securely (Apple allows only one download).

```sh
gh secret set ASC_KEY_ID --env ios-openwhispr-testflight
gh secret set ASC_ISSUER_ID --env ios-openwhispr-testflight
base64 -w0 /private/path/AuthKey_XXXXXXXXXX.p8 | \
  gh secret set ASC_PRIVATE_KEY_BASE64 --env ios-openwhispr-testflight
```

Also create an app record in App Store Connect for the main bundle ID, accept
required agreements and configure internal testers. An API key does not create
an app record or satisfy agreements automatically in this workflow. Each upload
uses the workflow run number/attempt as CFBundleVersion; if the app already has
higher build numbers, adjust that policy before uploading.

Future enhancement: automated certificate/profile provisioning through a
suitably authorized team API key. Do not assume that granting upload access alone
also grants Certificates, Identifiers & Profiles management access.

## Troubleshooting

- **No matching profiles/certificate:** all three profiles must match your team,
  IDs, distribution certificate and requested export method.
- **App Groups entitlement missing:** assign the group to every App ID and
  regenerate the profiles.
- **App won't install:** use Ad Hoc, include this device's UDID, enable Developer
  Mode and unlock the device. An App Store/TestFlight IPA cannot be sideloaded by
  the Tailscale helper as an Ad Hoc build.
- **Xcode/prebuild/native dependency error:** first reproduce with an unsigned
  build, examine its log and the recorded source/Xcode versions. No dependency
  patch should be approved solely to make a signing job green.
- **Upload succeeded, no TestFlight build:** inspect App Store Connect processing
  messages, compliance questions and version/build-number requirements.
