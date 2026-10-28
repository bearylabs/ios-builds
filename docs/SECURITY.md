# Security model

- This is a private build-control repository, not a public build service.
- Only manual build dispatches on the default branch are permitted. PRs trigger
  Linux validation only, never a signing build.
- App manifests allowlist source repositories. The selected source ref is
  resolved to a SHA before checkout; dependency lockfiles and upstream build
  scripts are still part of the reviewed supply chain.
- Build jobs receive no Apple secrets. Signing uses a new ephemeral macOS runner
  with only this repository's trusted scripts and the unsigned archive artifact
  from the same workflow run. No npm, Bundler, CocoaPods or source build hooks are
  executed in the signing job.
- Source artifacts remain untrusted input to Apple tooling; job separation
  reduces exposure but is not a complete sandbox or supply-chain guarantee.
  The uploaded application itself can be malicious: review what you build.
- An optional SOURCE_READ_TOKEN is scoped to source checkout/ref resolution. It
  should be a read-only fine-grained token, never a broad personal access token.
- Actions are pinned to commit SHAs. Review updates before replacing pins.
- Separate signing environments isolate app/distribution profiles. Configure
  branch restrictions and approval rules where the GitHub plan permits them.
  Private environment reviewer support is not available on every plan.
- Signing imports the P12 into a temporary keychain. Cleanup always attempts to
  delete it, installed profiles and API-key files. Hosted runners are ephemeral;
  an abrupt runner loss can prevent cleanup from executing.
- Artifacts contain only the unsigned archive/provenance or signed IPA/provenance;
  certificate/private-key/profile input ZIPs are never uploaded. An IPA embeds
  provisioning profiles as required by iOS, which can reveal registered UDIDs.
- Keep repository access restricted. Never expose arbitrary shell commands as
  workflow inputs or accept signing requests from untrusted forks.
- API credentials, provider keys, pairing records and certificate material must
  stay out of Git. GitHub secret masking is defense-in-depth, not permission to
  print secrets. Revoke/rotate anything accidentally exposed.

## Current limitations

The first native build and unsigned-archive export are not yet device-tested.
Manual provisioning requires periodic profile/certificate renewal. The setup
cannot guarantee that upstream cloud services accept custom app identities.
The optional Xcode path and pinned source commit must be maintained as runners
and upstream dependencies evolve. No automatic TestFlight tester distribution,
App Store submission or API-based certificate provisioning is implemented.
