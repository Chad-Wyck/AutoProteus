---
name: Bug report
about: Something behaves differently than the code or docs say it should
labels: bug
---

## What happened

<!-- A plain description of the wrong behavior. Quote exact error text. -->

## What you expected

<!-- What the documentation or code led you to expect instead. -->

## Reproduction

<!-- The smallest steps that reproduce it, from a clean checkout.
     If it involves a study or evaluation, name the script and the exact
     command line (redact keys and host paths). -->

1.
2.
3.

## Your evidence

- Version / commit:
- Platform and Python version:
- Ordinary suite on your checkout
  (`python -X utf8 -m unittest discover -s tests -q`):
  discovered ___ / passed ___ / failed ___ / errors ___ / skipped ___
- VM suite run? If yes: selection, counts, and host (KVM/WHPX).
  If no, say so — an unreproduced-on-VM note is useful, not a defect.
- Relevant log excerpt (attach the file if it is long; remove credentials,
  host paths and private artifacts first):

## Scope

<!-- Which area does this touch? autoproteus/ · controller/ · guest/ ·
     web/ · evaluations/ · tests/ · examples/ · docs -->

## Anything you did *not* check

<!-- Honest gaps help triage: platforms not tried, suites not run,
     configurations not tested. -->
