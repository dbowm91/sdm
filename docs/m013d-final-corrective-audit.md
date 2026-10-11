# M013d bootstrap repair and source integration audit

Status: implementation complete; PR #2 is open. Hosted PR CI run [38111257896](https://github.com/dbowm91/sdm/actions/runs/38111257896) on head `ffe295b6fd9c9bb73291cd9e61f0e935d162bfe0` passed all ten jobs, including pinned-history replay on each verification host. The main merge and merged-main verification are outstanding. See the [formal closure](../plans/closure/general-decision-model-framework/013d-status.md).

Baseline: `dbowm91/sdm@03c4a982219ffa830b7c0aba9dbb19a541cae56c` on `work/plans-sdm-m013c-qualification-gate-hardening`\
Implementation: `ca540c2f77917a608f1c2fa2fb01119317bfd3ca`, `246ee355031a921d44f7bd69964a477f1831fad7`, `17089c2ff659a5601e11227bd8710c139d0d4b0e`, `435cef7f7f6da6a017d33c4e3742e9920b3ec94b`, and `ffe295b6fd9c9bb73291cd9e61f0e935d162bfe0`\
Main/base and merge-base: `2bd0d5af16d143828dcbce7f411b8f3b675e7be`\
PR: [#2](https://github.com/dbowm91/sdm/pull/2), targeting `main`

The M013b `quantile` helper now validates inputs and sorts a copy before linear interpolation. Its bootstrap keeps seed 14014, 10,000 draws, 95% confidence, group resampling, and output shape. New tests compare two non-degenerate populations against both M013c's sorted bootstrap and the frozen M013a sorting behavior. They also cover degenerate/zero/one-group populations, invalid arguments, deterministic group ordering, and provenance links.

The pinned old checkout reproduced these original hashes exactly. The M013b evaluator file hashes to `161b1881efeb7750d8b5308d603cf318f5f16579d1db8d51739bbb8ba356cedb` at both pinned commit `11ea106c9af3b1ec362a98e709b530cc0fa137d0` and baseline `03c4a982219ffa830b7c0aba9dbb19a541cae56c`. The M013c evaluator file hashes to `edab5ff23238b58cb4441aee96d227073bf78911e61b0c97a35c55e36fc68e07` at pinned commit `8dd8a2151ef0c5b88adf5ce0c164992636bc17ee` and baseline `03c4a982219ffa830b7c0aba9dbb19a541cae56c`.

| Original artifact | SHA256 |
|---|---|
| M013a `quality-analysis.json` | `411ac0915a0dd6ae94710271b1b23bbad830732762b956dcca71500b6f592d6e` |
| M013b `m013a-audit-erratum.json` | `07fb99f1e984354a6746f3645f893beadfbbb3fd40ce4e37d4b6a834a0e15901` |
| M013b `m013b-diagnostics.json` | `3b489c25eb0fcd51b7dc08d7e9e7a1e1a45a6f16e244cf5a8173e8aceb728da4` |
| M013c `m013c-decision-audit.json` | `6560052ba93445288d1b7577c475d0fcaec12035d9838c8c955a91ced2801edf` |

Changing the M013b source changes the current erratum's embedded `input_sha256`; M013c then fingerprints that erratum. The regenerated M013b and M013c sidecar hashes therefore differ by design. `scripts/m013d_provenance_audit.py` records and compares these hashes, asserting semantic equivalence outside the source-hash map, historical preservation, and unchanged model dispositions. No frozen fixtures, trained artifacts, M013a protocol, historical report, or earlier closure record was edited.

The retained Binary disposition is **negative** and Choice is **indeterminate**. No new model qualification or final held-out inference was performed. The source integration is pending human review; no CodeGG pin, crates.io release, publication, or model promotion is authorized.
