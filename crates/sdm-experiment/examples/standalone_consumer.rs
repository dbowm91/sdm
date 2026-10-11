//! Minimal library consumer: deserialize a checked-in experiment config and
//! invoke the same public orchestration API as the `sdm` CLI.
use std::{env, fs};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = env::args()
        .nth(1)
        .ok_or("usage: standalone_consumer <experiment-config.json>")?;
    let spec: sdm_experiment::ExperimentSpec = serde_json::from_slice(&fs::read(path)?)?;
    let report = match spec.architecture.as_str() {
        "typed-binary" | "typed-choice" | "typed-score" => {
            serde_json::to_value(sdm_experiment::run_semantic(&spec)?)?
        }
        _ => serde_json::to_value(sdm_experiment::run(&spec)?)?,
    };
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}
