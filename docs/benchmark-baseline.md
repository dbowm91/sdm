# Runtime resource baseline

Measurement date: 2026-10-05. Host: macOS 26.6, x86_64 process (Rosetta), Rust
1.98.1, 24 GiB physical memory. This is a reproducible local baseline, not a
cross-machine service objective. Run `cargo run -p sdm-runtime --example benchmark
-- fixtures/benchmark-rank-request.json artifacts/compatibility-rank-v1.json`.

Artifact `sha256:b9484ce8b8afe2b345693e084468c89a628462e86faf1e9683c28ee53de6597e`
is 2,560 bytes. Cold local load took 510 μs. The benchmark ran 200 warm requests at
each candidate count; observed p50/p95 are:

| Candidates | p50 | p95 |
|---:|---:|---:|
| 16 | 289 μs | 291 μs |
| 64 | 1.132 ms | 1.139 ms |
| 128 | 2.269 ms | 2.317 ms |
| 256 | 4.554 ms | 4.624 ms |

Malformed-artifact rejection took 45 μs. Process peak RSS after warmup was 4,878,336
bytes. This is `getrusage` high-water RSS, not an isolated allocation delta. The old
CodeGG unit benchmark guards 1,000 one-candidate `hashed-linear-v1` calls under one
second; the run on this host completed in 7.676 ms (7.676 μs per one-candidate call).
For comparison, SDM's 16-candidate p50 is 289 μs and p95 is 291 μs; the workloads are
not equivalent because the CodeGG test has one candidate and excludes generic request
validation/response construction. The measurable runtime cost is recorded as a
regression against the old microbenchmark, with no production latency budget claimed:
the artifact remains unqualified and the backend is opt-in.
