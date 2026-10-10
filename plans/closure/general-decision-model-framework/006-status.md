# M006 closure — Qualification and portability corrective

Status: conditionally closed; remaining qualification depth is tracked by ready M007
Implementation commit: `ee0f613`

## Requirement-to-evidence

| Requirement | Evidence | Result |
| --- | --- | --- |
| Bounded streaming ingest and leakage audit | M002 closure records capped JSONL and exact/near duplicate audit; text similarity is advisory and not family/semantic proof | Pass with stated limits |
| Grouped uncertainty | M003 closure records grouped Rank MRR, recall@k and NDCG intervals | Partial: no slice-aware calibration or frozen four-semantic corpus |
| Runtime nonlinear v2 registration and parity | `load_artifact` dispatches nonlinear v2; schema/feature/calibration identity checks and runtime/model scorer parity test | Pass (mechanics only) |
| Atomic checkpoint and resume identity | Feature-gated checkpoint save/load verifies schema fingerprint and seed identity | Pass (optimizer state not persisted) |
| CPU resource/performance evidence | `benchmark_nonlinear` emits model/artifact digests, load time, p50/p95 at 1/16/64/128/256 candidates, RSS, artifact size and malformed-input rejection. Local run: artifact 8,675 bytes; cold load 1,143 µs; p95 23/336/1,293/2,628/5,245 µs; peak RSS 4,837,376 bytes | Pass locally (Rosetta x86_64 only) |
| Cross-platform runner coverage | CI matrix schedules Ubuntu x86_64, Ubuntu ARM64 and macOS Apple Silicon and uploads linear/nonlinear benchmark JSON | Pending hosted workflow results |
| CodeGG qualification | No approved independent CodeGG corpus or consumer adapter; M005 remains explicitly indeterminate | Correctly gated |

## Verification and limitations

- `rtk cargo fmt --all` — pass.
- `rtk cargo check -p sdm-runtime --examples --locked` — pass.
- `rtk cargo test --workspace --all-features --locked` — pass (20 tests, 16 suites).
- `rtk cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` — pass.
- `rtk cargo run -p sdm-runtime --example benchmark_nonlinear --` — pass; output above.
- Local host is Apple Silicon hardware under an x86_64 Rust toolchain/Rosetta; no native ARM64 conclusion is drawn.
- No CodeGG source, pin, fixtures or data changed. Compatibility must be rerun against the exact commit.

The nonlinear lexical projection is not a semantic encoder. This benchmark uses deterministic
initialized parameters, not trained capacity comparisons; it establishes resource mechanics,
not effectiveness. Slice-aware calibration, frozen multi-semantic qualification data,
trained-context ablations and hosted-runner outputs are assigned to M007. No promotion or
deployment approval is implied.

## Disposition

M006 is conditionally closed because the actionable generic ingestion/runtime safeguards,
local benchmark and hosted CI configuration are implemented and locally verified. M007 is
ready for residual generic evidence work. M005 remains indeterminate solely for lack of an
approved independent CodeGG corpus and CodeGG-owned adapter; no such material is fabricated
or inferred from compatibility fixtures.
