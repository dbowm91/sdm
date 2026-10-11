# SDM M012 — Post-M011 Release and Branch Reconciliation Corrective

Status: conditionally closed (source/PR handoff complete; publication blocked pending human/legal sign-off)
Class: corrective infrastructure / release readiness
Baseline: dbowm91/sdm@f9ce89765a1cb07ce23100177d8f56c30e52777d
Parent work line: work/plans-sdm-standalone-framework-m008-m011
Target integration base: main@8139b064bdcf3212e8f6fd912e801a479b55751c (revalidate before executing)
Planning governance: plans/003-planning-process.md
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md
Architectural authority: plans/adrs/ADR-0001-general-framework-and-model-boundaries.md; plans/adrs/ADR-0002-standalone-framework-before-consumer-qualification.md
Predecessor: plans/closure/general-decision-model-framework/011-status.md
Hard dependencies: M011 closed (yes); no CodeGG dataset or consumer adapter required
Operational dependencies: any legal compatibility sign-off and publication/merge decision belong to reviewers; no automatic deployment authorization

## 1. Why this corrective is necessary

The M011 closure explicitly calls SDM a reviewable standalone release candidate, not a merged, published or consumer-approved library. The repository default branch main is still the October 5, 2026 three-crate baseline; current development is the completed seven-crate M001–M011 history on work/plans-sdm-standalone-framework-m008-m011. There are no PRs recorded at planning. Hosted CI was green at the latest development SHA f9ce89765a1c; its release checks are evidence of mechanics, not permission to promote any learned decision model.

Specific unclosed release issues from M011:
- All seven workspace crate Cargo.toml manifests currently omit standard publish-facing description, documentation, homepage and repository metadata; root [workspace.package] has only version/edition/license/rust-version.
- cargo package --workspace --locked --allow-dirty verified the workspace but emitted metadata warnings. The package contents, registry dependency order and consumer usability from a clean packaged-source boundary still need deliberate review; the standalone consumer test currently uses path dependencies.
- scripts/audit_cargo_licenses.py asserts that each of the 34 locked packages has a nonempty license field. It does not analyze SPDX compatibility, dual-license selection, notices, attribution or distribution obligations.
- SHA-256 ensures artifact identity/corruption detection, not publisher authenticity. Publishing or accepting external weights is not part of current guarantees.
- M011 recorded negative Binary OOD evidence, Choice majority-baseline tie, 0/35 changed Choice predictions on counterfactual target flips, 8/22 no-answer recall, and insufficient OOD groups for Choice/Rank. These must stay visible as non-qualification warnings, rather than be erased by release labels.

The existing CodeGG v1 compatibility fixture has twelve validated and eleven runnable requests, and its checked-in legacy model digest is sha256:b9484ce8b8afe2b345693e084468c89a628462e86faf1e9683c28ee53de6597e. CodeGG continues to pin SDM@8139b064bdcf3212e8f6fd912e801a479b55751c. No approved independent CodeGG training/held-out corpus exists.

## 2. Objective

Prepare one reviewable source integration of the independently usable SDM framework into main, close publication-facing metadata and package smoke gaps, and capture sufficient evidence to decide whether to merge and/or later publish. No release/tag/merge/publication is performed by this handoff until its required review decision and verification have been completed.

This is a release-process corrective, not a model-quality successor, architecture redesign or CodeGG integration task.

## 3. Scope and explicit non-goals

In scope: branch/history reconciliation, workspace and crate release metadata, dependency/SPDX license review records, offline package/independent consumer smoke, docs/CLI/format reconciliation, security provenance disclaimers, reproducibility verification and review PR readiness.

Out of scope: fixing Binary OOD or Choice prediction quality, increasing parameter count, model distillation, new dataset/model training campaigns, CodeGG dataset generation, altering CodeGG SDM pin, publishing crates.io packages, creating tags/releases, automated merging, artifact signing implementation, replacing the existing artifact ABI or changing frozen synthetic/test gates to pass.

No M011 negative result or indeterminate outcome may be rewritten; any follow-up model quality experiments must be a separately scoped roadmap item. No model is declared fit for application deployment.

## 4. Work packages (one bounded corrective pass)

### A. Verify history and branch state

1. Inspect the live GitHub main and both predecessor work branches, Git tree/merge-base, PRs, tags and CI before editing. Confirm main has not advanced; rebase or reconcile only with an explicit no-force-push plan if it has.
2. Preserve the complete M001–M011 implementation commits, artifacts, authored/synthetic provenance, ADRs and closure records. Avoid cherry-picking duplicated commits from the old M001–M005 branch into the M008–M011 successor (the latter already descends from it).
3. Prepare a clean integration diff against main, checking that only intended SDM framework files land. Summarize commit lineage and any duplicated/stale documents. Keep the public default branch unchanged until a separately approved merge action.
4. Continue implementation on a branch descended from this planning SHA; do not overwrite an active implementation branch or force-update main.

### B. Publication and packaging metadata (seven crates)

1. Add accurate, consistent repository, description, documentation, homepage (only if verified), README/keywords/categories as appropriate to every workspace package; inherit common fields through [workspace.package] where supported by the declared Rust/Cargo MSRV. Preserve license = MIT and original contributor attribution. Do not invent a domain or documentation URL.
2. Preserve versioned path dependencies for the seven internal crates. Determine topological crates.io publication ordering for a future optional release, separating the release candidate from a user-approved publish action.
3. Review cargo package --list for each package and verify that included data, schemas, examples, generated artifacts and fixture paths are correct, and that neither sensitive datasets, target build outputs nor credentials are accidentally packaged. Do not add private user data.
4. Run packaging checks from a clean tracked checkout without --allow-dirty where practical; note any unavoidable repository-state difference. Validate that a packaged-source or staged consumer compiles using exactly the intended public crate entrypoints, not accidentally the workspace's source tree or local path resolution. Where registry publication is needed to test a dependency, record a separate operational gate instead of pushing to crates.io.

### C. License and artifact trust review

1. Enumerate direct/transitive dependencies with locked versions, exact SPDX expressions, actual selected licensing branches for dual-license packages, license text/attribution requirements and redistributed material; include the inherited Anomalyco copyright/provenance and any generated fixtures.
2. Extend the metadata-only audit to produce a reviewable third-party-notices/license inventory and fail on missing/ambiguous metadata, while explicitly distinguishing automated metadata checks from legal approval. An unresolved license requires a named human/legal review gate; never claim an automated script grants legal clearance.
3. Document that model/artifact digests establish identity and integrity, not trusted publisher authenticity. Require independently verified full Git SHA or trusted delivery channel for consumers. Preserve explicit offline-only/no-auto-download behavior and bounded artifact parse validation. Signing and trust-store implementation are future, not silently assumed.

### D. Documentation, interfaces and correctness reconciliation

1. Reconcile README, plans/README.md, plans/registry.md, artifact and typed-task docs with the actual implemented seven crates and CLI syntax. Fix obsolete references to M001 being ready or M008–M011 being unimplemented, and update any stale 'three-crate' historical wording only in current-facing text; never rewrite historical closure outcomes.
2. Publish an independent Quickstart for training, packaging, loading and evaluating synthetic Binary/Choice/Score/Rank models, with a stable examples/standalone-consumer smoke test and bounded error/failure/abstention semantics. Clearly separate legacy v1, additive v2 typed runtimes and unsupported semantic/model combinations.
3. Document output reproducibility scope (including host-dependent floating-point model hashes), public APIs/semver and extension points, platform evidence, performance measurement definitions, data/privacy import boundaries, and model-quality caveats (especially Binary/Choice and underpowered OOD slices). No marketing text describing synthetic success as production readiness.
4. Verify no application authority crossed into SDM, and no runtime-only train/eval/network/GPU dependency leaks. Any breaking schema/API issue discovered here is a stop and separately planned corrective, not a late implicit rewrite.

### E. CI, review PR and release gate

1. Re-run locked format, all-feature tests, strict Clippy, declared Rust 1.89 MSRV check, runtime-only cargo check/tree, package validation, named CLI end-to-end experiments, and standalone consumer compile on the integration candidate.
2. Require hosted Linux x86_64, Linux ARM64 and Apple Silicon verification, the same Linux-trained artifact loaded and checked on all three, frozen v1 CodeGG compatibility 12/11 and unchanged legacy artifact SHA, and M011 held-out protocol/generator/data fingerprint integrity. Report all failures or missing hosted artifacts honestly; do not merely cite previous green CI.
3. Add a non-publishing package/metadata/license inventory check to CI or release validation with a clear locally repeatable command. Keep any registry operation disabled by default.
4. Produce a reviewable GitHub pull request from the verified integration candidate into main with a concise history/diff/risk summary, acceptance matrix, artifacts, and retained negative model-evidence links. PR creation is a handoff artifact, not merge authorization.
5. Record the merge decision as pending human review even when CI succeeds. Do not merge, tag or publish as an implicit consequence of package verification. If main advanced, reconcile and rerun CI before any merge recommendation.

## 5. Failure, concurrency, restart and security semantics

The planning branch, current implementation branch and main are independent mutable refs: use a known expected head SHA for any pushes and detect updates rather than overwriting another agent's work. Never force-push protected history or rewrite M001–M011 closures. Package or docs generation writes to temporary locations and does not replace frozen training/held-out files. Release verification is read-only with respect to production registries and downstream CodeGG; no automated provider call, telemetry, session capture, model download or real-user data import.

Publish metadata are untrusted data fields until reviewers verify their destinations. Dependency inventory alone cannot establish legal compatibility. No package step should execute downloaded model code. All release claims must distinguish static artifact integrity, verified source revision and actual signed provenance.

## 6. Verification commands and focused gates

Run, capture result and link hosted logs for:

~~~sh
cargo fmt --all -- --check
cargo test --workspace --all-features --locked
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
cargo check -p sdm-runtime --locked
cargo tree -p sdm-runtime --locked
cargo run -q -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json
cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked
cargo package --workspace --locked
cargo metadata --locked --format-version 1
~~~

Continue running the six documented sdm-experiment configs and the frozen M011 v2 generator/split/protocol checks with bounded output paths, and the three-host trained-artifact portability benchmark already defined in .github/workflows/ci.yml. Add per-crate package --list audit and newly required license inventory/metadata checks. A clean-checkout cargo package succeeds without an unaddressed metadata warning, or the exception is recorded explicitly as a block to registry publication. Verify artifact contents and consumer execution rather than treating a successful dry run alone as proof.

Focused negative guards: missing repository/description metadata, changed CodeGG model digest, runtime training-dependency contamination, package leaking private files, spoofed license claims, undocumented breaking schema, stale README, test-set provenance drift, non-working staged consumer and unexpected main ancestry.

## 7. Closure and decision gates

Only close M012 if: the final integration branch/PR is reviewable and has no unresolved merge conflict; all seven crate manifests have accurate metadata and a verified package path; third-party license inventory and any required human sign-off are documented; current docs match actual code; clean locked and hosted matrix checks pass; immutable CodeGG v1 fixture/digest evidence remains intact; and closure explicitly retains M011 negative/indeterminate predictive-quality findings.

If legal review cannot be obtained, mark release-publication **blocked** while source integration may still be reviewable; do not falsely close publication readiness. If a packaging or compatibility failure exists, leave M012 active/blocked and register an exact corrective. A successful M012 does not itself merge the PR, publish to crates.io, retarget CodeGG, authorize a learned model or remove M005's independent corpus gate.

Write plans/closure/general-decision-model-framework/012-status.md with: implementation SHA(s), main and source ancestry/merge-base, PR URL/state, per-crate manifest/package outcomes, SPDX/notices and sign-off disposition, command results/host logs, 3-target metrics, legacy compatibility and hash, output model/training/held-out report identities, negative quality evidence, security/ABI/privacy review, outstanding severity-ranked risks, and explicit merge/publication decisions. Update registry and roadmap only based on observed evidence. Do not retroactively change M011 closure.
