# Standalone SDM quickstart

SDM trains and evaluates models from explicitly named local datasets and
experiment configurations. Its outputs describe model behavior for the supplied
data; they do not grant application permissions or establish application
effectiveness.

## Run a reproducible synthetic experiment

From the repository root, run one of the checked-in configurations:

```sh
mkdir -p target/experiments
cargo run --locked -p sdm-experiment -- experiment run \
  --config fixtures/synthetic-binary-typed-v1.experiment.json
```

The command validates the config and dataset, uses the frozen group split,
trains from train cases, selects calibration on dev cases, packages and reloads
the artifact, and reports metrics on held-out test cases. Output paths are
explicit in the config; existing artifact/report outputs are not overwritten.
Repeat with the Choice, Score, or Rank configs listed in the repository
[README](../README.md#build-and-qualify). These checked-in datasets are
synthetic mechanics examples.

## Load an artifact

The public runtime validates bounded local artifact bytes and the caller's
task/schema before inference. It returns errors for malformed data, unsupported
architecture/task combinations, and invalid inputs; callers retain authority
over candidate eligibility, abstention handling, fallback, and any action.
Load bytes through the public dispatcher:

```rust
let bytes = std::fs::read("target/experiments/binary.artifact.json")?;
let artifact = sdm_runtime::load_artifact(&bytes)?;
match artifact {
    sdm_runtime::LoadedArtifact::UnsupportedV2(envelope) => {
        return Err(std::io::Error::new(
            std::io::ErrorKind::Unsupported,
            format!("unsupported architecture: {}", envelope.architecture),
        ).into());
    }
    supported => {
        // Dispatch the validated variant to the matching request/task API.
        let _ = supported;
    }
}
```

The [standalone consumer](../examples/standalone-consumer/) demonstrates
consuming the experiment library through public Rust APIs. CI also extracts the
Cargo package archives and compiles this consumer against those staged package
contents, with internal crate dependencies resolved by package name/version.
That check catches workspace-path leakage without publishing packages.

For future crates.io distribution, internal package dependency order is:

1. `sdm-core`
2. `sdm-data` and `sdm-nonlinear`
3. `sdm-eval`, `sdm-runtime`, and `sdm-training`
4. `sdm-experiment`

The order is a dependency-topological candidate only. It does not authorize
registry publication. Every crate currently has version `0.1.0`; coordinated
version changes must preserve compatible internal dependency constraints.

## Compatibility and quality limits

Legacy v1 LinearArtifact loading remains supported. The additive typed v2
runtime supports only the architecture/task combinations it registers; other
combinations return an explicit unsupported result rather than being coerced.
Inference is bounded and offline. A digest identifies bytes and detects
corruption, but does not authenticate a publisher; consumers should obtain
source/artifacts through a trusted channel and verify the full source commit.

Deterministic seeds and frozen inputs make experiment procedures repeatable,
but independently trained floating-point artifacts can have host-dependent
byte hashes. See [reproducibility](reproducibility.md) for scope. The M011
synthetic evidence includes negative Binary OOD results, a Choice majority
baseline tie and no prediction changes on 35 tested target flips, low Choice
no-answer recall, and underpowered Choice/Rank OOD slices. Those outcomes remain
qualification limitations; synthetic mechanics do not establish production
readiness.

Public API compatibility follows explicit artifact/schema versions and normal
Rust semver expectations. Extension points are the declared semantic request
types, feature schema, runtime architecture registry, and experiment config;
applications must not infer support for undeclared combinations. See
[typed task heads](typed-task-heads.md), [artifact format](artifact-format.md),
and the M011 [qualification record](../plans/closure/general-decision-model-framework/011-status.md).
