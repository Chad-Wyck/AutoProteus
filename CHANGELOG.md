# Release notes

Versions use `major.minor.patch`. Before launch, `0.x.0` introduces features and
`0.x.y` contains bug fixes. Components can exceed 9 or 99. Historical `0.0.x`
release and experiment labels remain unchanged.

## 0.2.0

- Separate `seed.py invoke` from the development test suite. Support workspace
  JSON argument files to reduce shell quoting, and preserve `check --tool`.
- Split prompts, context construction and file-edit mechanics into small seed
  modules while preserving Workspace and the two-file capability recipe.
- Separate frozen study preparation/calibration from trial execution/reporting.
  Include the new runner module in trusted fingerprints and cache identities.
- Add an opt-in supplied-parent growth comparison that withholds final inputs
  until independent verification and activation. Keep its verdicts distinct
  from the existing strict visible-input preservation baseline.
- Keep edit previews, syntax feedback and context variants opt in. Live 9B
  qualification remains deferred; these changes establish no model success rate.

## 0.1.0

- Add optional workflow experiments for edit feedback, syntax feedback, older
  observations and focused development/use stages, with frozen plans and
  independent grading. Keep these treatments outside the default seed.
- Strengthen grader fault controls and provide practical offline task fixtures.
  Distinguish model-reported completion from scoped host checks in the interface.
- Fit native tool history against the actual provider representation while
  retaining human instructions, the newest exchange and host resource limits.
- Recover human provenance at the broker before translating tool results;
  literal `ACTION RESULT` requests survive pruning, Resume and activation.
- Key input calibration by its exact existing/absent capability requirements.
  Enforce a shared deadline through development, grading, retention and use;
  report shutdown overrun and cleanup separately.
- Preserve the six-model exploratory findings. New Qwen/OxCoder comparisons are
  prepared and validated without starting live-model trials.
