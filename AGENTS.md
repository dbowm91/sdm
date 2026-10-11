# Repository agent guidance

- Prefix shell commands with `rtk`; see the shared RTK instructions supplied to this workspace.
- Preserve frozen fixture bytes, split manifests, historic report hashes, and closure records. New experiments use unique `target/` outputs.
- Keep the runtime offline and independent of training crates, and add new artifact behavior under a new architecture identifier.
- For predictive-quality work, do not inspect final test outcomes until generator, groups, protocol, gates, candidate set, and support report are frozen and committed. Do not use a held-out cohort for selection or retuning.
- Read the relevant milestone plan and architecture docs before changing behavior. Update `README.md`, `docs/artifact-format.md`, `docs/typed-task-heads.md`, and the plan registry when architecture or milestone status changes.
