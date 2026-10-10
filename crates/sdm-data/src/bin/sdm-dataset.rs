use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeSet,
    env, fs,
    io::{Read, Write},
    path::Path,
};

#[derive(Serialize, Deserialize)]
struct Bundle {
    provenance: sdm_data::Provenance,
    examples: Vec<sdm_data::DatasetExample>,
}

fn read_bundle(path: &str) -> Result<Bundle, String> {
    let mut bytes = Vec::new();
    fs::File::open(path)
        .map_err(|e| e.to_string())?
        .take((sdm_data::MAX_DATASET_BYTES + 1) as u64)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    if bytes.len() > sdm_data::MAX_DATASET_BYTES {
        return Err("dataset exceeds byte limit".into());
    }
    serde_json::from_slice(&bytes).map_err(|e| e.to_string())
}
fn atomic_write(path: &str, bytes: &[u8]) -> Result<(), String> {
    let target = Path::new(path);
    let parent = target.parent().unwrap_or(Path::new("."));
    let tmp = parent.join(format!(".sdm-dataset-{}.tmp", std::process::id()));
    let mut f = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&tmp)
        .map_err(|e| e.to_string())?;
    f.write_all(bytes).map_err(|e| e.to_string())?;
    f.sync_all().map_err(|e| e.to_string())?;
    fs::rename(&tmp, target).map_err(|e| e.to_string())
}
fn run() -> Result<(), String> {
    let args: Vec<_> = env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("validate") if args.len() == 3 => {
            let bundle = read_bundle(&args[2])?;
            let hash = sdm_data::validate_dataset(&bundle.examples, &bundle.provenance)
                .map_err(|error| error.to_string())?;
            println!("validated {} examples {hash}", bundle.examples.len());
            Ok(())
        }
        Some("split") if args.len() >= 5 => {
            let bundle = read_bundle(&args[2])?;
            let hash = sdm_data::validate_dataset(&bundle.examples, &bundle.provenance)
                .map_err(|error| error.to_string())?;
            let seed = args[3].parse::<u64>().map_err(|error| error.to_string())?;
            let mut excluded_families = BTreeSet::new();
            let mut test_families = BTreeSet::new();
            let mut index = 5;
            while index < args.len() {
                let flag = args[index].as_str();
                let family = args.get(index + 1).ok_or_else(|| "family flag requires a value".to_string())?.clone();
                match flag {
                    "--exclude-family" => { excluded_families.insert(family); }
                    "--test-family" => { test_families.insert(family); }
                    _ => return Err(format!("unknown split option {flag}")),
                }
                index += 2;
            }
            let split = sdm_data::freeze_splits_with_family_holdouts(
                &bundle.examples,
                &hash,
                seed,
                &excluded_families,
                &test_families,
            )
            .map_err(|error| error.to_string())?;
            sdm_data::validate_split(&bundle.examples, &split, &hash)
                .map_err(|error| error.to_string())?;
            let bytes = serde_json::to_vec_pretty(&split).map_err(|error| error.to_string())?;
            atomic_write(&args[4], &bytes)?;
            println!("wrote frozen split {}", split.fingerprint);
            Ok(())
        }
        _ => Err("usage: sdm-dataset validate <bundle.json> | split <bundle.json> <seed> <manifest.json> [--exclude-family NAME] [--test-family NAME]".into()),
    }
}
fn main() {
    if let Err(e) = run() {
        eprintln!("sdm-dataset: {e}");
        std::process::exit(2)
    }
}
