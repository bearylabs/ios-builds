# Security model for a public build repository

## Visibility and access

- Repository contents, workflow logs, job summaries and provenance are public.
  Only **public source repositories** are supported; the resolver explicitly
  checks visibility and rejects private sources. Do not configure a source PAT.
- Archive, IPA and signing-log artifacts are public **ciphertext**, not plaintext.
  Signed IPAs embed profiles that may contain device UDIDs. Encrypting the whole
  IPA protects that information from artifact readers.
- The build runner has only the public age recipient. The private identity is
  backed up locally and stored as an environment secret in signing environments.
- No raw Xcode log files are uploaded as artifacts. Dependency/compiler output
  remains visible in Actions, so no confidential source/configuration or provider
  credentials may enter a build. Signing and TestFlight output are redirected to
  local files and published only as encrypted diagnostic ZIPs.

## Execution and signing boundaries

- Only manual build dispatches on the default branch are permitted. PRs trigger
  Linux validation only, never signing. There is no `pull_request_target` workflow.
- App manifests allowlist source repositories. A selected source ref resolves to
  a SHA before checkout. Dependency lockfiles and upstream scripts still require
  review; a public source repository is not automatically trustworthy.
- Build jobs receive no Apple secrets or private artifact identity. Signing uses
  a new ephemeral runner with trusted control scripts and an encrypted archive
  from the same workflow run. It executes no npm/Bundler/CocoaPods source hooks.
- The archive is still untrusted input to Xcode/Apple tooling. This reduces
  exposure but is not a complete sandbox or supply-chain guarantee. The app
  itself could be malicious: review what you build and install.
- Signing environments are restricted to `main` and require owner approval.
  Administrator bypass is disabled; self-review is allowed because this setup
  has a single owner. Repository writers can alter workflows on main, so write
  access is itself a high-trust capability. Reassess approval rules for a team.
- API/certificate/profile/age secrets are environment secrets, not repository
  secrets. Signing remains disabled via IOS_SIGNING_ENABLED until Apple setup.
- Actions and the downloaded age release are pinned; age downloads are checked
  against platform-specific SHA-256 digests. Review updates before changing pins.

## Cleanup and operations

- The P12 is imported into a temporary keychain. Cleanup always attempts to remove
  keychain, profiles, API files, plaintext archive/IPA and sensitive logs. An abrupt
  runner loss can prevent cleanup, but GitHub-hosted runners are ephemeral.
- Encryption failure fails the job; there is no plaintext artifact fallback.
- Artifacts expire after seven days. Downloaded/decrypted IPAs and logs must remain
  private. Age key rotation does not decrypt old artifacts; retain old identities
  while their artifacts are needed. Back up the local identity securely.
- Public-repository standard GitHub-hosted runners are generally free under
  GitHub's policies. Larger runners/other services can be billable. Fork PRs do
  not gain secrets; keep GitHub's first-time contributor approval protections.

## Current limitations

The first native build and unsigned-archive export are not yet device-tested.
Manual provisioning requires periodic profile/certificate renewal. The setup
cannot guarantee upstream cloud services accept custom app identities. Xcode
versions and pinned source commits need maintenance. No automatic API-based
certificate provisioning, tester assignment or App Store submission is provided.
Encryption is artifact confidentiality, not a guarantee against a malicious
maintainer, reviewed source dependency or compromised runner/toolchain.
