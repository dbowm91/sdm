use serde::{Deserialize, Serialize};
use std::{env, fs};

#[derive(Deserialize)]
struct Input {
    protocol: sdm_eval::QualificationProtocol,
    dataset_sha256: String,
    split_fingerprint: String,
    artifact_sha256: String,
    calibration_sha256: String,
    examples: Vec<sdm_data::DatasetExample>,
    predictions: Vec<sdm_eval::RankPrediction>,
}
#[derive(Serialize)]
struct Gate {
    status: String,
    observed: Option<f64>,
    minimum: f64,
}
#[derive(Serialize)]
struct Report {
    verdict: String,
    protocol_sha256: String,
    dataset_sha256: String,
    split_fingerprint: String,
    artifact_sha256: String,
    metrics: sdm_eval::RankMetrics,
    gates: std::collections::BTreeMap<String, Gate>,
}
fn run() -> Result<(), String> {
    let args: Vec<_> = env::args().collect();
    if args.len() != 2 {
        return Err("usage: sdm-qualify <frozen-input.json>".into());
    }
    let bytes = fs::read(&args[1]).map_err(|e| e.to_string())?;
    if bytes.len() > 64 * 1024 * 1024 {
        return Err("input exceeds 64 MiB".into());
    }
    let input: Input = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
    input
        .protocol
        .validate(
            &input.dataset_sha256,
            &input.split_fingerprint,
            &input.artifact_sha256,
            &input.calibration_sha256,
        )
        .map_err(|e| e.to_string())?;
    if input.examples.len() < input.protocol.minimum_cases {
        return Err("insufficient cases for preregistered minimum".into());
    }
    let metrics =
        sdm_eval::evaluate_rank(&input.examples, &input.predictions, input.protocol.rank_k)
            .map_err(|e| e.to_string())?;
    let gates = input
        .protocol
        .gates
        .iter()
        .map(|(name, minimum)| {
            let observed = match name.as_str() {
                "mrr_min" => metrics.mrr,
                "recall_at_k_min" => metrics.recall_at_k,
                "ndcg_min" => metrics.ndcg,
                "precision_min" => metrics.precision,
                "recall_min" => metrics.recall,
                "f1_min" => metrics.f1,
                _ => None,
            };
            let status = match observed {
                Some(v) if v >= *minimum => "pass",
                Some(_) => "fail",
                None => "indeterminate",
            };
            (
                name.clone(),
                Gate {
                    status: status.into(),
                    observed,
                    minimum: *minimum,
                },
            )
        })
        .collect::<std::collections::BTreeMap<_, _>>();
    let verdict = if gates.values().any(|g| g.status == "fail") {
        "fail"
    } else if gates.values().any(|g| g.status == "indeterminate") {
        "indeterminate"
    } else {
        "pass"
    };
    let report = Report {
        verdict: verdict.into(),
        protocol_sha256: input.protocol.fingerprint,
        dataset_sha256: input.dataset_sha256,
        split_fingerprint: input.split_fingerprint,
        artifact_sha256: input.artifact_sha256,
        metrics,
        gates,
    };
    println!(
        "{}",
        serde_json::to_string_pretty(&report).map_err(|e| e.to_string())?
    );
    Ok(())
}
fn main() {
    if let Err(e) = run() {
        eprintln!("sdm-qualify: {e}");
        std::process::exit(2)
    }
}
