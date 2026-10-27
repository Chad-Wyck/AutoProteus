## Summary

<!-- What changes, and why. One change per PR; link the issue if there is one. -->

## Scope

<!-- Areas touched: autoproteus/ · controller/ · guest/ · web/ ·
     evaluations/ · tests/ · examples/ · docs.
     App-specific integrations belong outside the core until the post-v1
     extension library — flag here if this is one. -->

## Evidence

<!-- Keep this proportional to the change. For documentation-only work,
     describe the links/instructions checked and note suites not run.
     For code changes, report relevant tests and exact results. -->

- Commit checked:
- Platform / Python, if applicable:
- Checks performed (links, instructions, tests):
- Ordinary suite, if run (`python -X utf8 -m unittest discover -s tests -q`):
  discovered ___ / passed ___ / failed ___ / errors ___ / skipped ___ / ___s
- VM suite (if run): selection ___ · counts ___ · host (KVM/WHPX) ___
- New or changed tests in this PR:
- What I did **not** run, and why:

## House rules check

<!-- Mark checks that do not apply as N/A and briefly explain. -->

- [ ] Standard library only — no new dependencies
- [ ] Rejects unauthorized host operations; preserves bounded error recovery
- [ ] No guest/candidate code imported or executed on the host
- [ ] No secrets or private artifacts in the diff; private host paths redacted
      (use supported protected credential storage or `AUTOPROTEUS_API_KEY`)
- [ ] Skips reported as skips; scripted/fixture results not described
      as live-model outcomes

## Security note

<!-- Required if this touches isolation, the broker, providers, file
     handling or the web UI: what does the change do to the boundary
     described in SECURITY.md? Write "No boundary impact" only if true. -->
