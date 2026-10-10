use std::{env, fs, io::Read};

fn main() {
    if let Err(error) = run() {
        eprintln!("sdm: {error}");
        std::process::exit(2);
    }
}
fn run() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = env::args().collect();
    if args.len() != 5 || args[1] != "experiment" || args[2] != "run" || args[3] != "--config" {
        return Err("usage: sdm experiment run --config PATH".into());
    }
    let path = &args[4];
    let mut bytes = Vec::new();
    fs::File::open(path)?
        .take((sdm_experiment::MAX_CONFIG_BYTES + 1) as u64)
        .read_to_end(&mut bytes)?;
    if bytes.len() > sdm_experiment::MAX_CONFIG_BYTES {
        return Err("config exceeds byte bound".into());
    }
    let spec: sdm_experiment::ExperimentSpec = serde_json::from_slice(&bytes)?;
    let result = sdm_experiment::run(&spec)?;
    println!("{}", serde_json::to_string_pretty(&result)?);
    Ok(())
}
