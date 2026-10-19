# Determined: focused review for AutoProteus

19 October 2026, America/Regina. Reviewed [bartanderson/Determined](https://github.com/bartanderson/Determined) at commit `31f3337848416bc23cc99b0b82b90a2d644b58fe`, with a focus on completion contracts, context assembly, source analysis, freshness and related regression tests. Compared against AutoProteus HEAD `aed23d3b73d304c32ae86a9b247fc947c7f4e502` plus the existing uncommitted v0.2.1 fixture correction and completed v0.2.0 findings.

This is a static source review. No Determined code or tests were executed, and no dependency, application feature or model setting was installed or changed. A separate example packet was assembled from current AutoProteus source using only standard-library parsing; no project modules were imported.

## Assessment

**The quoted idea is a strong fit as a small experiment.** A source-grounded editing packet could reduce invented APIs, incomplete tool registration and repeated searching. The exact implementation is more limited than the quoted description suggests, and its names should not imply formal correctness.

The most useful adaptation is to assemble the facts needed for one concrete edit, using the selected model and existing guest tools. Determined provides useful examples of what to include; adopting its full analysis application is unnecessary for testing the idea.

## What the linked function actually does

[`completion_contract`](https://github.com/bartanderson/Determined/blob/31f3337848416bc23cc99b0b82b90a2d644b58fe/determined/agent/agent_tools.py#L5540) reads an indexed function record and produces:

- A reconstructed signature from stored parameter annotations and return type.
- Caller names and locations, plus callee/dependency names.
- A split between known stubs and other callee references.
- Stored behavioral descriptions, with a docstring fallback.
- Retrieved design guidance when available.

It does **not** itself include the complete target implementation, caller bodies or a general registration map. Its optional projection flag currently gathers context and appends a pointer to another tool; that branch does not actually generate the suggested implementation described by the interface documentation.

The richer path is [`export_context`](https://github.com/bartanderson/Determined/blob/31f3337848416bc23cc99b0b82b90a2d644b58fe/determined/agent/export_context.py#L232), using [`build_brief`](https://github.com/bartanderson/Determined/blob/31f3337848416bc23cc99b0b82b90a2d644b58fe/determined/agent/sketch_stub.py#L710). It adds caller-body excerpts, similar nearby implementations and available class APIs. It can accumulate follow-up context and distinguish internally obtained output from supplied text. This combination is closer to the proposal in the other chat.

The exporter is oriented toward classified stubs and external-model escalation. AutoProteus's missing capabilities often have no stub yet: the required edit spans an existing dispatcher, its description table and a new test. A literal port would miss that common case.

## What is worth borrowing

**1. Show the actual interface before the model invents one.** Include the relevant public call and helper signatures, the dispatch location, a nearby working example and how tests invoke the interface. For an AutoProteus capability, that means `Workspace.execute`, `TOOL_SPECS`, the applicable text/path helpers and a small existing test pattern. This could address the recent model-written test calling an absent `Workspace.format_json` method. It remains a hypothesis until measured. [Local failure evidence](D:/AI_New/AP/evaluations/seed-v0.2.0-local-findings.md)

**2. Assemble relationships around the edit.** An outline tells the model where definitions are; an edit packet explains which definitions must change together. For a new file tool, include the dispatcher and schema together, relevant imports/helpers, requested defaults and preservation requirements. A static call graph alone cannot establish all of that. Determined has dedicated dynamic-dispatch analysis as well as ordinary call extraction; the linked completion function does not expose every relationship. [Dynamic-edge analysis](https://github.com/bartanderson/Determined/blob/31f3337848416bc23cc99b0b82b90a2d644b58fe/determined/ingestion/dynamic_edges.py#L35)

**3. Provide bounded evidence with a route to inspect more.** Determined's exporter caps individual caller/sibling excerpts and supplies follow-up commands. AutoProteus can use its existing character-offset reads and literal search for further inspection. Add a total packet limit, explicit omitted sections and exact source references; line caps alone do not bound a long line or an accumulated session. The source packet must remain task data, not a replacement for the original user request.

**4. Refresh context as the seed changes.** Determined supports re-ingestion and dependent-file discovery. AutoProteus already records source identities; reuse those identities for packet freshness and invalidate evidence after an included file changes. For the initial small seed, assembling from current files avoids a persistent database and its maintenance. [Re-ingestion](https://github.com/bartanderson/Determined/blob/31f3337848416bc23cc99b0b82b90a2d644b58fe/determined/ingestion/reingest_file.py)

## Implementation details that should not be carried over unchanged

**Symbol identity needs more than a name.** The completion function selects one function by name with `LIMIT 1`; its contract lookup is also name-based. That is ambiguous when modules or classes reuse names. The exporter accepts file/class hints, but some downstream brief queries still use the symbol alone. Use a workspace-relative path, qualified symbol and source hash; report ambiguity instead of silently choosing a record. [Completion lookup](https://github.com/bartanderson/Determined/blob/31f3337848416bc23cc99b0b82b90a2d644b58fe/determined/agent/agent_tools.py#L5559), [brief construction](https://github.com/bartanderson/Determined/blob/31f3337848416bc23cc99b0b82b90a2d644b58fe/determined/agent/sketch_stub.py#L744)

**Read exact signatures from source.** The parser's stored parameter-type mapping covers annotated ordinary parameters. The completion function reconstructs its displayed signature from that mapping, so unannotated parameters and defaults are not reliably represented. Defaults and optional arguments have already caused AutoProteus failures. A compact literal definition header is preferable to this reconstruction. [Function extraction](https://github.com/bartanderson/Determined/blob/31f3337848416bc23cc99b0b82b90a2d644b58fe/determined/ingestion/parse_ast.py#L252)

**Separate observations from inferred constraints.** Behavioral records come partly from docstrings and simple AST/text patterns; design guidance is retrieved through semantic similarity. These are useful hints, not independently verified preconditions or proof that a proposed edit is valid. A missing design section can mean unavailable analysis. Preserve the user's contract and independent checks as authority. [Behavioral extraction](https://github.com/bartanderson/Determined/blob/31f3337848416bc23cc99b0b82b90a2d644b58fe/determined/ingestion/parse_ast.py#L1074), [design retrieval](https://github.com/bartanderson/Determined/blob/31f3337848416bc23cc99b0b82b90a2d644b58fe/determined/agent/agent_tools.py#L886)

**Keep unknown graph edges visible.** Caller/callee helpers support resolved-only filtering, but the completion function uses the default and does not display the resolution distinction. A reference not identified as a stub is not proof of an available implementation. Similarly, no recorded caller does not prove a function is unused. [Graph helpers](https://github.com/bartanderson/Determined/blob/31f3337848416bc23cc99b0b82b90a2d644b58fe/determined/agent/agent_tools.py#L404)

**Bind packets to a snapshot.** The completion entry point does not itself refresh the index or validate source hashes. The exporter mixes indexed facts with current source reads, and accumulated sessions are not keyed by source revision. Re-ingestion exists, but freshness still requires an explicit lifecycle. This matters particularly for an agent editing the code it will use next.

**Retain AutoProteus's edit protection.** Determined's replacement helper replaces the first occurrence. AutoProteus already rejects ambiguous matches, preserves surrounding bytes/line endings and returns conflict locations. That existing behavior is the appropriate baseline. [Determined editor](https://github.com/bartanderson/Determined/blob/31f3337848416bc23cc99b0b82b90a2d644b58fe/determined/agent/agent_tools.py#L7673), [AutoProteus edits](D:/AI_New/AP/autoproteus/file_ops.py:48)

## Fit with the current local project

AutoProteus already supplies a source map and capability recipe, exact edits, shared helper APIs, bounded section reads, a test-independent invoker and protected acceptance checks. Its experimental outline and inspection program already parse Python without importing it. The missing piece is **selecting and assembling those existing facts for the particular edit**. [Seed recipe](D:/AI_New/AP/SEED.md), [outline helper](D:/AI_New/AP/evaluations/source_navigation.py), [inspection program](D:/AI_New/AP/evaluations/inspect_workspace.py)

The completed navigation pilot had equal accepted-upgrade counts and no outline calls. A new optional context tool could also go unused. Initially supply a bounded packet directly as labelled task evidence and record whether it survives into the real provider request. This tests the packet/delivery treatment, not the isolated causal benefit of a call graph.

The v0.2.1 context-fixture correction is already present in the working tree. It is a prerequisite to fair qualification, not a new proposal here. Preserve original model verdicts and use new frozen evidence for later comparisons.

## Concrete example

The [review-only example packet](D:/AI_New/AP/evaluations/determined-edit-context-example-2026-10-19.json) contains:

- Current `Workspace.execute` dispatch excerpts.
- Five real Workspace API signatures, including defaults.
- Relevant schema-generation/source excerpts and a real test-call pattern.
- Public capability-recipe excerpts.
- Four file hashes, line/character locations and explicit coverage/freshness limits.

Its compact JSON form is **6,444 characters / 6,448 UTF-8 bytes**. This is a hand-selected illustration, not an installed extractor, a measured token saving or an optimized size. It contains no hidden grader data and invents no new feature requirement. An eventual implementation should generate comparable evidence inside the guest using bounded workspace reads and static parsing, without importing candidate modules.

## Smallest useful experiment

1. Validate packet accuracy offline: duplicate method/function names, defaults, keyword-only arguments, aliases/dynamic dispatch, edited or syntactically incomplete files, omitted relationships, Unicode/CRLF locations and hard size limits. Unknown relationships should be labelled, with ordinary reading still available.
2. Freeze the corrected starter and compare existing guidance with the same guidance plus a focused packet on unfamiliar capability contracts. Keep model/profile, action, output and wall allowances matched; charge packet construction and prompt costs.
3. Measure accepted upgrades, schema/dispatch agreement, invented helper calls, candidate-test failures, time to first useful edit, reading volume and complete task cost. Record final activation/use separately when required.
4. If useful, repeat with another model and fresh tasks before making it normal behavior. A later on-demand helper can be compared separately; it would add discovery and tool-selection demands.

Determined supplies ideas for **before-edit context**. GEPA supplies ideas for **diagnosing a failed attempt**, and Harness2 for **retaining reusable improvement lessons**. They fit a common workflow, while each should first be tested independently.

Focused regression sources reviewed include [completion contracts](https://github.com/bartanderson/Determined/blob/31f3337848416bc23cc99b0b82b90a2d644b58fe/tests/regression/test_completion_contract.py), [context export](https://github.com/bartanderson/Determined/blob/31f3337848416bc23cc99b0b82b90a2d644b58fe/tests/regression/test_export_context.py), [graph resolution](https://github.com/bartanderson/Determined/blob/31f3337848416bc23cc99b0b82b90a2d644b58fe/tests/regression/test_call_graph_accuracy.py) and [re-ingestion](https://github.com/bartanderson/Determined/blob/31f3337848416bc23cc99b0b82b90a2d644b58fe/tests/regression/test_reingest_file.py). Those tests are useful implementation evidence; they do not establish improved AutoProteus editing performance. The recurring eight-repository watchlist was not enlarged.
