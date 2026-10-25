# Model-selected stock tool — October 24, 2026

**Qwen wrote a useful new stock-processing tool, but the original autonomous
workflow remained incomplete because its handoff declaration was unusable.**
A separate posthoc check of unchanged code passed; it does not rescore that run.

The frozen task specified a concrete two-shop TSV reconciliation outcome and
JSON artifact, while the model chose the new tool name and argument interface.
It required a reusable seed extension; this does not test whether the model
independently decides that an extension is necessary. No tool name or two-option
capability menu was supplied. This is one directed discovery task, not broad
capability-discovery qualification or an autonomous two-generation chain.

The model chose combine_stock_files(input_a, input_b, output), added its dispatch
and schema, and created five focused tests. It requested activation after 26
actions and 4331 generated tokens in 467.48 seconds. It also produced the correct
visible sample summary during development. No deadline/token/action limit stopped
it, and no operator supplied feedback or repaired its code.

The declaration was saved as development/capability.json. Its arguments mapped
@INPUT_A to shops/east.tsv, and similarly for the other roles; the required format
instead placed placeholders in the chosen argument values. The original runner
looked for root capability.json and raised File not found before independent
grading or activation. Strict outcome: **0/1 completed workflows, original tool
verification not run**. This is not an independently demonstrated behavior defect.
The generic instruction to save capability.json could be clearer about location;
the reversed argument template is a separate interoperability failure.

## Separately labelled unchanged-code diagnostic

After the original attempt closed, the operator matched values in the model's
own development/combine_stock_args.json to its own role mapping. This yielded
input_a=@INPUT_A, input_b=@INPUT_B and output=@OUTPUT. That diagnostic template
was operator-selected; it was not the submitted handoff. No model request was
repeated, and no candidate code or saved declaration was edited.

A fresh disposable VM ran the unchanged candidate's full suite and held-out
registered-tool calls for duplicate aggregation, Unicode and an empty shop.
All three outcomes, argument declaration checks and input-byte preservation checks
passed. Static scope also passed: runtime edits stayed in the two permitted files,
one separate new test file was added and protected sources were unchanged.
This establishes useful functionality for those cases. It gives **no activation,
model-driven final-use or original completed-workflow credit**.

## Recording and follow-up

Both connection checks/calibration and the single model trial used the standard
native adapter with Qwen3.5 9B Q6_K, 128K context, 4K responses, temperature 0.6,
thinking off and no LoRA. Candidate execution used disposable VMs, with Internet
access disabled. The task shared 3600 seconds, 128 actions and 65536 generated
tokens across development/checking/use. Provider capture is complete: 27 calls,
255795 input tokens and 4331 generated tokens. Posthoc scripted checks are
additional diagnostic costs, with zero model inference.

The research runner now records missing, malformed or invalid declarations as
explicit unverified submission outcomes rather than crashing. The regression
reproduces the missing-path and reversed-placeholder cases. Original plan,
runner/probe bytes, invalid handoff, failure records and scores remain preserved;
no live trial was repeated under the fix. A later fresh study can compare a
simpler handoff or bounded public submission feedback, rather than adding more
instructions or a manifest requirement to the default seed.

Evidence: `.data/discovery-v090-20261024-r4/`, including `attempt/`,
`posthoc-unchanged-tool/`, frozen runner and cleanup. The model service stopped.
