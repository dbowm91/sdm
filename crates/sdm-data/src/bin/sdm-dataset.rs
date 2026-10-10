use serde::{Deserialize, Serialize};
use std::{collections::BTreeSet, env, fs, io::Write, path::Path};

#[derive(Serialize, Deserialize)]
struct Bundle {
    provenance: sdm_data::Provenance,
    examples: Vec<sdm_data::DatasetExample>,
}

fn read_bundle(path: &str) -> Result<Bundle, String> {
    let bytes = fs::read(path).map_err(|e| e.to_string())?;
    if bytes.len() > sdm_data::MAX_DATASET_BYTES {
        return Err("dataset exceeds byte limit".into());
    }
    serde_json::from_slice(&bytes).map_err(|e| e.to_string())
}
fn atomic_write(path: &str, bytes: &[u8]) -> Result<(), String> {
    let target = Path::new(path);
    let parent = target.parent().unwrap_or(Path::new("."));
    let tmp = parent.join(format!(".sdm-dataset-{}.tmp", std::process::id()));
    let mut f = fs::File::create(&tmp).map_err(|e| e.to_string())?;
    f.write_all(bytes).map_err(|e| e.to_string())?;
    f.sync_all().map_err(|e| e.to_string())?;
    fs::rename(&tmp, target).map_err(|e| e.to_string())
}
fn run() -> Result<(), String> {
    let args: Vec<_> = env::args().collect();
    match args.get(1).map(String::as_str){Some("validate")if args.len()==3=>{let b=read_bundle(&args[2])?;let hash=sdm_data::validate_dataset(&b.examples,&b.provenance).map_err(|e|e.to_string())?;println!("validated {} examples {hash}",b.examples.len());Ok(())},Some("split")if args.len()==5=>{let b=read_bundle(&args[2])?;let hash=sdm_data::validate_dataset(&b.examples,&b.provenance).map_err(|e|e.to_string())?;let seed=args[3].parse::<u64>().map_err(|e|e.to_string())?;let split=sdm_data::freeze_splits(&b.examples,&hash,seed,&BTreeSet::new()).map_err(|e|e.to_string())?;sdm_data::validate_split(&b.examples,&split,&hash).map_err(|e|e.to_string())?;let bytes=serde_json::to_vec_pretty(&split).map_err(|e|e.to_string())?;atomic_write(&args[4],&bytes)?;println!("wrote frozen split {}",split.fingerprint);Ok(())},_=>Err("usage: sdm-dataset validate <bundle.json> | split <bundle.json> <seed> <manifest.json>".into())}
}
fn main() {
    if let Err(e) = run() {
        eprintln!("sdm-dataset: {e}");
        std::process::exit(2)
    }
}
