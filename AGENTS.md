# Repository agent guidance

- Prefix shell commands with `rtk`; see the shared RTK instructions supplied to this workspace.
- Preserve frozen fixture bytes, split manifests, historic report hashes, and closure records. New experiments use unique `target/` outputs.
- Keep the runtime offline and independent of training crates, and add new artifact behavior under a new architecture identifier.
- For predictive-quality work, do not inspect final test outcomes until generator, groups, protocol, gates, candidate set, and support report are frozen and committed. Do not use a held-out cohort for selection or retuning.
- Read the relevant milestone plan and architecture docs before changing behavior. Update `README.md`, `docs/artifact-format.md`, `docs/typed-task-heads.md`, and the plan registry when architecture or milestone status changes.
# M014 evaluation boundary

The M014 qualification inputs are declared in `docs/m014-freeze-v1.json`. Before the freeze commit is recorded and verified, do not run any `fixtures/m014-final-*.experiment.json` config. Those configs evaluate the held-out test partition. After the freeze, run the frozen final set once; do not tune, rerun, or modify source, data, candidates, protocol, or gates in response to test results. Write outputs only under `target/m014/final/` and preserve the committed freeze inputs.
