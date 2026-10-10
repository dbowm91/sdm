//! Deterministic synthetic context/candidate interaction capacity and ablation run.
use sdm_nonlinear::{initialize, train, PairwiseModel};
use serde::Serialize;
use sha2::{Digest, Sha256};

const TOKENS: [&str; 4] = ["amber", "birch", "cobalt", "dune"];
type Example = (Vec<f64>, f64);
type ExampleSet = Vec<Example>;

#[derive(Serialize)]
struct CapacityResult {
    hidden_units: usize,
    parameter_count: usize,
    updated_parameter_count: usize,
    utilization_fraction: f64,
    epochs: usize,
    training_mse: f64,
    model_sha256: String,
    frozen_examples: usize,
    accuracy_full_context: f64,
    accuracy_masked_context: f64,
    accuracy_permuted_context: f64,
}

fn dataset(model: &PairwiseModel) -> Result<ExampleSet, Box<dyn std::error::Error>> {
    let mut result = Vec::new();
    for context in TOKENS {
        for candidate in TOKENS {
            let input = model.rank_features(context, candidate)?;
            let target = f64::from(context == candidate);
            result.push((input, target));
        }
    }
    Ok(result)
}

fn accuracy(
    model: &PairwiseModel,
    rows: &[Example],
    mode: &str,
) -> Result<f64, Box<dyn std::error::Error>> {
    let mut correct = 0;
    for (index, (input, target)) in rows.iter().enumerate() {
        let mut x = input.clone();
        match mode {
            "masked" => {
                for feature in (0..x.len()).step_by(3) {
                    x[feature] = 0.0;
                    x[feature + 2] = 0.0;
                }
            }
            "permuted" => {
                let offset = index % TOKENS.len();
                let old_context: Vec<_> = (0..TOKENS.len()).map(|token| input[token * 3]).collect();
                for token in 0..TOKENS.len() {
                    x[token * 3] = old_context[(token + offset) % TOKENS.len()];
                    x[token * 3 + 2] = x[token * 3] * x[token * 3 + 1];
                }
            }
            _ => {}
        }
        correct += usize::from((model.score(&x)? >= 0.5) == (*target >= 0.5));
    }
    Ok(correct as f64 / rows.len() as f64)
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let features: Vec<String> = TOKENS
        .iter()
        .flat_map(|t| [format!("ctx:{t}"), format!("cand:{t}"), format!("both:{t}")])
        .collect();
    let mut results = Vec::new();
    let mut frozen = None;
    for hidden in [4, 8] {
        let mut model = initialize(features.clone(), hidden, 20261010)?;
        let initial = model.clone();
        let rows = dataset(&model)?;
        let summary = train(&mut model, &rows, 1200, 0.04)?;
        let count = model.parameter_count()?;
        let updated = model
            .input_weights
            .iter()
            .zip(&initial.input_weights)
            .chain(model.hidden_bias.iter().zip(&initial.hidden_bias))
            .chain(model.output_weights.iter().zip(&initial.output_weights))
            .filter(|(trained, before)| (*trained - *before).abs() > 1e-12)
            .count()
            + usize::from((model.output_bias - initial.output_bias).abs() > 1e-12);
        results.push(CapacityResult {
            hidden_units: hidden,
            parameter_count: count,
            updated_parameter_count: updated,
            utilization_fraction: updated as f64 / count as f64,
            epochs: summary.epochs_completed,
            training_mse: summary.final_mse,
            model_sha256: summary.model_sha256,
            frozen_examples: rows.len(),
            accuracy_full_context: accuracy(&model, &rows, "full")?,
            accuracy_masked_context: accuracy(&model, &rows, "masked")?,
            accuracy_permuted_context: accuracy(&model, &rows, "permuted")?,
        });
        frozen = Some(rows);
    }
    let rows = frozen.expect("two capacity runs");
    let frozen_digest = format!("sha256:{:x}", Sha256::digest(serde_json::to_vec(&rows)?));
    println!(
        "{}",
        serde_json::to_string_pretty(&serde_json::json!({
            "protocol": "sdm-interaction-ablation-v1",
            "seed": 20261010,
            "learning_rate": 0.04,
            "training_examples": rows.len(),
            "evaluation_examples": rows.len(),
            "frozen_examples_sha256": frozen_digest,
            "target": "1 iff context token equals candidate token",
            "limitations": ["synthetic mechanics only", "same frozen examples used for SGD and ablation scoring; not held-out effectiveness evidence"],
            "capacities": results
        }))?
    );
    Ok(())
}
