use std::{env, fs, io::Read};

fn main() {
    if let Err(error) = run() {
        eprintln!("sdm: {error}");
        std::process::exit(2);
    }
}
fn run() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = env::args().collect();
    if args.len() != 5
        || args[1] != "experiment"
        || (args[2] != "run" && args[2] != "evaluate" && args[2] != "m015a-replay")
        || args[3] != "--config"
    {
        return Err("usage: sdm experiment (run|evaluate|m015a-replay) --config PATH".into());
    }
    let path = &args[4];
    let mut bytes = Vec::new();
    fs::File::open(path)?
        .take((sdm_experiment::MAX_CONFIG_BYTES + 1) as u64)
        .read_to_end(&mut bytes)?;
    if bytes.len() > sdm_experiment::MAX_CONFIG_BYTES {
        return Err("config exceeds byte bound".into());
    }
    if args[2] == "evaluate" {
        // Inference-only path: EvaluateSpec denies training fields, validates
        // exact artifact SHA before scoring, and never trains or rewrites bytes.
        let spec: sdm_experiment::EvaluateSpec = serde_json::from_slice(&bytes)?;
        let result = serde_json::to_value(sdm_experiment::run_evaluate(&spec)?)?;
        println!("{}", serde_json::to_string_pretty(&result)?);
        return Ok(());
    }
    if args[2] == "m015a-replay" {
        // M015a DEV-only final-action replay: read-only inference over the DEV
        // partition with source-provenance origins; never trains, never touches
        // test, never rewrites historical artifacts.
        let spec: sdm_experiment::m015a::M015aReplaySpec = serde_json::from_slice(&bytes)?;
        let result = serde_json::to_value(sdm_experiment::m015a::run_m015a_replay(&spec)?)?;
        println!("{}", serde_json::to_string_pretty(&result)?);
        return Ok(());
    }
    let spec: sdm_experiment::ExperimentSpec = serde_json::from_slice(&bytes)?;
    let result = match spec.architecture.as_str() {
        "typed-binary"
        | "typed-choice"
        | "typed-choice-cross"
        | "typed-choice-compositional"
        | "typed-score" => serde_json::to_value(sdm_experiment::run_semantic(&spec)?)?,
        _ => serde_json::to_value(sdm_experiment::run(&spec)?)?,
    };
    println!("{}", serde_json::to_string_pretty(&result)?);
    Ok(())
}
