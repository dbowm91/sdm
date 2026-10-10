# M006 closure — Qualification and portability corrective

Status: conditionally closed; remaining qualification depth is tracked by ready M007
Implementation commit: `ee0f613a9038884bf50efe4a6c4839a2a60dbb08`

## Requirement-to-evidence

| Requirement | Evidence | Result |
| --- | --- | --- |
| Bounded streaming ingest and leakage audit | M002 closure records capped JSONL and exact/near duplicate audit; text similarity is advisory and not family/semantic proof | Pass with stated limits |
| Grouped uncertainty | M003 closure records grouped Rank MRR, recall@k and NDCG intervals | Partial: no slice-aware calibration or frozen four-semantic corpus |
| Runtime nonlinear v2 registration and parity | `load_artifact` dispatches nonlinear v2; schema/feature/calibration identity checks and runtime/model scorer parity test | Pass (mechanics only) |
| Atomic checkpoint and resume identity | Feature-gated checkpoint save/load verifies schema fingerprint and seed identity | Pass (optimizer state not persisted) |
| CPU resource/performance evidence | `benchmark_nonlinear` emits model/artifact digests, load time, p50/p95 at 1/16/64/128/256 candidates, RSS, artifact size and malformed-input rejection. Local run: artifact 8,675 bytes; cold load 1,143 µs; p95 23/336/1,293/2,628/5,245 µs; peak RSS 4,837,376 bytes | Pass locally (Rosetta x86_64 only) |
| Cross-platform runner coverage | GitHub Actions run [38076997293](https://github.com/dbowm91/sdm/actions/runs/38076997293) passed all checks and uploaded benchmarks for Ubuntu x86_64, Ubuntu ARM64 and macOS Apple Silicon | Pass |
| CodeGG qualification | No approved independent CodeGG corpus or consumer adapter; M005 remains explicitly indeterminate | Correctly gated |

## Verification and limitations

- `rtk cargo fmt --all` — pass.
- `rtk cargo check -p sdm-runtime --examples --locked` — pass.
- `rtk cargo test --workspace --all-features --locked` — pass (20 tests, 16 suites).
- `rtk cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` — pass.
- `rtk cargo run -p sdm-runtime --example benchmark_nonlinear --` — pass; output above.
- Hosted CI run 38076997293 — all 3 matrix jobs passed fmt, all-feature tests, strict Clippy, runtime/example checks, dependency-tree inspection and both benchmarks.
- Hosted nonlinear p95 µs at 1/16/64/128/256 candidates: Linux x86_64 11/195/906/1,508/3,243; Linux ARM64 25/387/1,530/3,129/6,176; Apple Silicon 54/326/3,319/6,105/9,937. Cold load: 760/1,698/3,559 µs respectively. RSS readings are platform-specific (`ru_maxrss`) and not directly comparable (25,325,568 / 24,514,560 / 2,670,592 bytes).
- Identical model digest `sha256:fc3bb30ddbf4f87fd55cb6c60e07cfa0b5946f2f0c3252e3eeb8eccdb1a8e48b`; identical artifact digest `sha256:fbfa1f9d4fa483ffc19ff6abd9f6e270f0325f36525b1d9b171f7bf76b56eb21`; 500 samples per candidate count. This is initialized synthetic model mechanics, not trained-model quality.
- Local host is Apple Silicon hardware under an x86_64 Rust toolchain/Rosetta; native Apple Silicon evidence comes from hosted macOS CI.
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
