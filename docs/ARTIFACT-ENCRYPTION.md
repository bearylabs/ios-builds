# Encrypted artifacts in a public build repository

## What is public?

Workflows, app manifests, source refs, public build metadata and dependency/build
logs are public. This repository supports **public source only** and must never
be used to bundle provider credentials or confidential configuration.

Unsigned archives, IPAs (including embedded Ad Hoc UDIDs) and signing diagnostics
are uploaded **only after age encryption**. The public build runner knows only
the recipient; it cannot decrypt. Apple secrets and the artifact identity exist
only in the app/distribution signing environments. TestFlight receives a normal
IPA directly from the ephemeral signing runner, not through a public artifact.

Encryption protects stored artifact content, not against malicious reviewed
build scripts, compromised tooling or code with maintainer access. Review your
source and workflow changes.

## Local key (already configured for this repository)

The setup generates a private identity **outside Git**:

```text
~/.local/share/ios-build-signing/artifacts.agekey
```

Its directory is mode 700; the identity is mode 600. Make a secure backup. Losing
all copies makes retained artifacts undecryptable. The local age tools are at:

```text
~/.local/share/ios-build-signing/age-tools/age/age
~/.local/share/ios-build-signing/age-tools/age/age-keygen
```

A new installation can install the pinned tool without sudo:

```sh
mkdir -p ~/.local/share/ios-build-signing
chmod 700 ~/.local/share/ios-build-signing
RUNNER_TEMP="$HOME/.local/share/ios-build-signing" bash scripts/install-age.sh
# Only if no identity exists; never overwrite an existing key.
umask 077
~/.local/share/ios-build-signing/age-tools/age/age-keygen \
  -o ~/.local/share/ios-build-signing/artifacts.agekey
```

Configure the public recipient and private environment identities from this repo:

```sh
~/.local/share/ios-build-signing/age-tools/age/age-keygen \
  -y ~/.local/share/ios-build-signing/artifacts.agekey | \
  gh variable set ARTIFACT_AGE_RECIPIENT

gh secret set ARTIFACT_AGE_IDENTITY --env ios-openwhispr-ad-hoc \
  < ~/.local/share/ios-build-signing/artifacts.agekey
gh secret set ARTIFACT_AGE_IDENTITY --env ios-openwhispr-testflight \
  < ~/.local/share/ios-build-signing/artifacts.agekey
```

The private identity must be an **environment secret**, never a repository secret.
Both environments should require owner approval and allow only `main` deployments.
With a single owner, self-review must remain allowed so the owner can approve
manually dispatched builds. Prevent administrator bypass where supported.

## Download and decrypt

```sh
gh run download RUN_ID --pattern 'openwhispr-ad-hoc-*' --dir downloads
find downloads -name '*.ipa.age'
umask 077
~/.local/share/ios-build-signing/age-tools/age/age \
  --decrypt --identity ~/.local/share/ios-build-signing/artifacts.agekey \
  --output downloads/OpenWhispr.ipa /path/to/downloaded/OpenWhispr.ipa.age
~/dev/apple-dev-setup/iphone-wifi install "$PWD/downloads/OpenWhispr.ipa"
```

For an unsigned archive, decrypt `archive.zip.age` to a ZIP and extract locally.
It is still unsigned and cannot be installed. For signing diagnostics, decrypt
`signing-diagnostics.zip.age` and inspect the contained logs locally; do not post
those logs publicly without redaction.

All encrypted artifacts expire after seven days. The `downloads/` directory and
`*.agekey` are ignored by Git, but ignore rules are not a substitute for keeping
secrets outside the checkout. Key rotation requires updating the public variable
and both environment secrets together; preserve old keys for older artifacts.
