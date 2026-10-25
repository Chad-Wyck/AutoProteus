# v0.10.0 preparation

This revision implements completion guidance and compatibility changes. It does
not establish better live-model task completion; no new live-model study ran.

- After a genuine internal activation, use a 411-character final-use recipe
  instead of the 1,705-character development guidance. Later human requests
  restore development guidance. Keep every original requirement and permission.
- Place current activation state before observations, once per request, including
  the protected fallback for older seeds. Preserve the full journal and existing
  concise-handoff/recovery behavior.
- Compare explicit optional arguments against declared schema defaults and show
  differing values beside results. Never infer undeclared defaults, change an
  argument or treat a schema declaration as proof of implementation correctness.
  Override notices sit outside the returned tool data to avoid contaminating
  copied artifacts.
- Extend the third-identical-result hint to every tool, including model-added
  capabilities. Do not suppress calls or assume repeated effects are harmless.
- Keep response normalization in the protected adapter. Native-mode prose now
  displays and waits for input; it never counts as completed work. Complete
  textual `finish` and neutral JSON actions are accepted; malformed, partial and
  ambiguous call envelopes still fail validation. Existing completion grading
  and connection qualification still require the corresponding explicit outcomes.
- Replace the filtered datalist and two preset cards with an installed-model
  select and custom/download entry. Verified all eight installed names, a 9B
  selection and custom entry in the browser without changing the saved model.
- Use hidden console Python and a retained process handle for Windows startup,
  wait for a terminated child before reading its status, and preserve nonzero
  failures. The original empty-log popup could not be reproduced. Controlled
  success/failure diagnostics and reopening the actual app both passed.

The seed gains no module or provider-specific protocol branch. The source guide
was condensed to 11,703 characters including saved CRLF line endings, below its
12,000-character whole-file read limit. Copied research variants preserve the
new active-use guidance; new comparisons require regenerated source fingerprints.

Validation:

- 395 ordinary tests: 343 passed, 52 platform/opt-in skips.
- Full scripted VM suite: 26 passed, one live-public-web check skipped.
- After final cleanup: four targeted VM checks passed (protected starter suite,
  concise activation, the short-guidance variant, and override envelopes with
  intact operation acknowledgements).
- JavaScript syntax and diff whitespace checks passed.
- Replayed all three immutable responses from the user's failed 4B "Testing"
  session: each now displays its reply and waits, with zero actions and no false
  completion. This is recorded-response replay, not fresh inference.
- Reloaded the idle app through authenticated shutdown and the Windows launcher;
  verified v0.10.0, VM isolation, the original saved model and eight installed
  model names. Historical session outcomes were not edited or regraded.

Local logs: `.data/current-revision-unit-verified.log`,
`.data/current-revision-vm-final.log`, `.data/current-revision-vm-followup.log`,
and `.data/format-diagnostic-20261024/normalization-replay.json`.
