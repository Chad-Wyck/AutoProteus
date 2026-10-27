## Summary

<!-- What changes, and why. One change per PR; link the issue if there is one. -->

## Scope

<!-- Areas touched: autoproteus/ · controller/ · guest/ · web/ ·
     evaluations/ · tests/ · examples/ · docs.
     App-specific integrations belong outside the core until the post-v1
     extension library — flag here if this is one. -->

## Evidence

<!-- Review starts here. Give exact numbers, not adjectives. -->

- Commit tested:
- Platform / Python:
- Ordinary suite (`python -X utf8 -m unittest discover -s tests -q`):
  discovered ___ / passed ___ / failed ___ / errors ___ / skipped ___ / ___s
- VM suite (if run): selection ___ · counts ___ · host (KVM/WHPX) ___
- New or changed tests in this PR:
- What I did **not** run, and why:

## House rules check

- [ ] Standard library only — no new dependencies
- [ ] Fails closed on unknown/malformed input; no permissive fall-through
- [ ] No guest/candidate code imported or executed on the host
- [ ] No secrets, host paths or private artifacts in the diff
      (keys belong in `AUTOPROTEUS_API_KEY`, never in files)
- [ ] Skips reported as skips; scripted/fixture results not described
      as live-model outcomes

## Security note

<!-- Required if this touches isolation, the broker, providers, file
     handling or the web UI: what does the change do to the boundary
     described in SECURITY.md? Write "No boundary impact" only if true. -->
