use sdm_training::{read_jsonl, train};
use std::{env, fs, path::Path};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = env::args().skip(1).collect();
    if args.len() < 2 || args.len() > 4 {
        return Err("usage: sdm-train <dataset.jsonl> <artifact.json> [seed] [epochs]".into());
    }
    let seed = args.get(2).map(|x| x.parse()).transpose()?.unwrap_or(1u64);
    let epochs = args
        .get(3)
        .map(|x| x.parse())
        .transpose()?
        .unwrap_or(20usize);
    let (cases, _) = read_jsonl(Path::new(&args[0]))?;
    let (artifact, report) = train(&cases, seed, epochs)?;
    fs::write(&args[1], serde_json::to_vec(&artifact)?)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}
