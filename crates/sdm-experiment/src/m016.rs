//! M016 TinyMLP trainer (deterministic, bounded, CPU-only).
//!
//! Trains `sdm-typed-choice-tinymlp-v1` (shared tanh scorer + symmetric
//! answerability) on M015 TRAIN/DEV ONLY. No FINAL, no held-out tuning.
//! All randomness is seeded; two replicas with same seed produce identical bytes.
//!
//! `run_m016_train` adds the bounded grid harness (<=36 configs), DEV-only
//! candidate selection on a predeclared final-action objective, threshold
//! calibration, eval-time ablations, feature export for the isolated tree
//! baseline, and atomic artifact/report writes.

use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    io::Read,
    path::Path,
    time::Instant,
};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use sdm_data::{validate_dataset, validate_split, DatasetExample, Provenance, SplitManifest};
use sdm_runtime::tinymlp::{TinyMlpPayload, TINYMLP_ACTIVATION, TINYMLP_HIDDEN_WIDTHS};

use crate::ExperimentError;

#[derive(Debug, Clone)]
pub struct TinyMlpConfig {
    pub hidden_width: usize,
    pub learning_rate: f64,
    pub l2: f64,
    pub epochs: usize,
    pub seed: u64,
    pub lambda_answerability: f64,
}

impl TinyMlpConfig {
    pub fn validate(&self) -> Result<(), String> {
        if !TINYMLP_HIDDEN_WIDTHS.contains(&self.hidden_width) {
            return Err("hidden width must be 32 or 64".into());
        }
        if !(self.learning_rate.is_finite()
            && self.learning_rate > 0.0
            && self.learning_rate <= 1.0)
        {
            return Err("learning rate must be in (0,1]".into());
        }
        if !(self.l2.is_finite() && self.l2 >= 0.0 && self.l2 <= 1.0) {
            return Err("l2 must be in [0,1]".into());
        }
        if self.epochs == 0 || self.epochs > 500 {
            return Err("epochs must be 1..=500".into());
        }
        if !(self.lambda_answerability.is_finite() && self.lambda_answerability >= 0.0) {
            return Err("lambda must be finite non-negative".into());
        }
        Ok(())
    }
}

/// Analytic gradients: (gw1, gb1, gw2, gb2, gans_w, gans_b, loss).
type MlpGradients = (Vec<f64>, Vec<f64>, Vec<f64>, f64, Vec<f64>, f64, f64);

/// Deterministic xorshift64* RNG (no external deps, reproducible across hosts).
#[derive(Debug, Clone)]
struct XorShift64 {
    state: u64,
}

impl XorShift64 {
    fn new(seed: u64) -> Self {
        Self {
            state: seed.wrapping_add(0x9E3779B97F4A7C15).max(1),
        }
    }
    fn next_u64(&mut self) -> u64 {
        let mut x = self.state;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.state = x;
        x.wrapping_mul(0x2545F4914F6CDD1D)
    }
    fn next_f64(&mut self) -> f64 {
        // Uniform in [0,1)
        ((self.next_u64() >> 11) as f64) / ((1u64 << 53) as f64)
    }
    fn uniform(&mut self, lo: f64, hi: f64) -> f64 {
        lo + (hi - lo) * self.next_f64()
    }
}

/// One training case: encoded context (D), encoded candidates (each D),
/// target (Some(idx) or None), all finite and bounded.
#[derive(Debug, Clone)]
pub struct TinyMlpExample {
    pub context: Vec<f64>,
    pub candidates: Vec<Vec<f64>>,
    pub target: Option<usize>,
}

fn sigmoid(z: f64) -> f64 {
    1.0 / (1.0 + (-z).exp())
}

/// Forward pass returning (scores, hidden activations per candidate, answerability).
fn forward(
    params: &TinyMlpParams,
    context: &[f64],
    candidates: &[Vec<f64>],
) -> (Vec<f64>, Vec<Vec<f64>>, f64) {
    let h = params.hidden;
    let mut scores = Vec::with_capacity(candidates.len());
    let mut hiddens = Vec::with_capacity(candidates.len());
    for cand in candidates {
        let mut hidden = vec![0.0; h];
        for (j, hj) in hidden.iter_mut().enumerate() {
            let mut z = params.b1[j];
            for (i, x) in context.iter().chain(cand.iter()).enumerate() {
                z += x * params.w1[i * h + j];
            }
            *hj = z.tanh();
        }
        let mut s = params.b2;
        for (hh, w) in hidden.iter().zip(&params.w2) {
            s += hh * w;
        }
        scores.push(s);
        hiddens.push(hidden);
    }
    // Symmetric answerability: mean/max pooling.
    let d = context.len();
    let mut mean = vec![0.0; d];
    let mut max = vec![f64::NEG_INFINITY; d];
    for c in candidates {
        for (i, x) in c.iter().enumerate().take(d) {
            mean[i] += *x;
            if *x > max[i] {
                max[i] = *x;
            }
        }
    }
    let n = candidates.len().max(1) as f64;
    for m in &mut mean {
        *m /= n;
    }
    let mut z = params.ans_bias;
    for (i, x) in context
        .iter()
        .chain(mean.iter())
        .chain(max.iter())
        .enumerate()
    {
        z += x * params.ans_weights[i];
    }
    (scores, hiddens, sigmoid(z))
}

#[derive(Debug, Clone)]
struct TinyMlpParams {
    hidden: usize,
    dim: usize,
    w1: Vec<f64>,
    b1: Vec<f64>,
    w2: Vec<f64>,
    b2: f64,
    ans_weights: Vec<f64>,
    ans_bias: f64,
}

impl TinyMlpParams {
    fn init(dim: usize, hidden: usize, seed: u64) -> Self {
        let mut rng = XorShift64::new(seed);
        // Xavier for tanh: U(-sqrt(6/(fan_in+fan_out)), +...).
        let fan_in = (2 * dim) as f64;
        let limit_w1 = (6.0 / (fan_in + hidden as f64)).sqrt();
        let w1: Vec<f64> = (0..2 * dim * hidden)
            .map(|_| rng.uniform(-limit_w1, limit_w1))
            .collect();
        let limit_w2 = (6.0 / (hidden as f64 + 1.0)).sqrt();
        let w2: Vec<f64> = (0..hidden)
            .map(|_| rng.uniform(-limit_w2, limit_w2))
            .collect();
        let limit_ans = (6.0 / ((3 * dim) as f64 + 1.0)).sqrt();
        let ans_weights: Vec<f64> = (0..3 * dim)
            .map(|_| rng.uniform(-limit_ans, limit_ans))
            .collect();
        Self {
            hidden,
            dim,
            w1,
            b1: vec![0.0; hidden],
            w2,
            b2: 0.0,
            ans_weights,
            ans_bias: 0.0,
        }
    }

    /// Analytic gradients for one example (BCE ans + lambda*CE choice).
    /// Returns (gw1, gb1, gw2, gb2, gans_w, gans_b, loss).
    #[allow(clippy::too_many_arguments)]
    fn gradients(
        &self,
        context: &[f64],
        candidates: &[Vec<f64>],
        target: Option<usize>,
        lambda: f64,
    ) -> MlpGradients {
        let h = self.hidden;
        let (scores, hiddens, a) = forward(self, context, candidates);
        let y_ans = if target.is_some() { 1.0 } else { 0.0 };
        let a_clamped = a.clamp(1e-15, 1.0 - 1e-15);
        let loss_ans = -y_ans * a_clamped.ln() - (1.0 - y_ans) * (1.0 - a_clamped).ln();
        let dlogit_ans = a - y_ans; // d BCE / d logit

        // Answerability grads: input is [ctx, mean, max].
        // (Gradients here are w.r.t. head weights, so no routing through the
        // max-pool argmax is needed; mean/max values are the head inputs.)
        let d = self.dim;
        let n = candidates.len().max(1) as f64;
        let mut mean = vec![0.0; d];
        let mut max = vec![f64::NEG_INFINITY; d];
        for c in candidates {
            for (i, x) in c.iter().enumerate().take(d) {
                mean[i] += *x;
                if *x > max[i] {
                    max[i] = *x;
                }
            }
        }
        for m in &mut mean {
            *m /= n;
        }
        let mut gans_w = vec![0.0; 3 * d];
        for (i, x) in context
            .iter()
            .chain(mean.iter())
            .chain(max.iter())
            .enumerate()
        {
            gans_w[i] = dlogit_ans * x;
        }
        let gans_b = dlogit_ans;

        let mut gw1 = vec![0.0; self.w1.len()];
        let mut gb1 = vec![0.0; h];
        let mut gw2 = vec![0.0; h];
        let mut gb2 = 0.0;
        let mut loss_choice = 0.0;

        if let Some(t) = target {
            // Softmax CE grads.
            let max_s = scores.iter().copied().fold(f64::NEG_INFINITY, f64::max);
            let exps: Vec<f64> = scores.iter().map(|s| (s - max_s).exp()).collect();
            let sum: f64 = exps.iter().sum();
            let probs: Vec<f64> = exps.iter().map(|e| e / sum).collect();
            loss_choice = -probs[t].clamp(1e-15, 1.0).ln();
            for (k, (prob, hidden)) in probs.iter().zip(&hiddens).enumerate() {
                let desired = if k == t { 1.0 } else { 0.0 };
                let dscore = (prob - desired) * lambda;
                gb2 += dscore;
                // Backprop through output layer to hidden.
                for j in 0..h {
                    gw2[j] += dscore * hidden[j];
                    // Backprop through tanh: d = dscore * w2[j] * (1 - h_j^2).
                    let dh = dscore * self.w2[j] * (1.0 - hidden[j] * hidden[j]);
                    gb1[j] += dh;
                    let cand = &candidates[k];
                    for (i, x) in context.iter().chain(cand.iter()).enumerate() {
                        gw1[i * h + j] += dh * x;
                    }
                }
            }
        }

        (
            gw1,
            gb1,
            gw2,
            gb2,
            gans_w,
            gans_b,
            loss_ans + lambda * loss_choice,
        )
    }
}

/// Train TinyMLP on encoded examples. Returns payload (without threshold;
/// caller calibrates threshold on DEV via `select_threshold`).
pub fn train_tinymlp(
    train: &[TinyMlpExample],
    dim: usize,
    config: &TinyMlpConfig,
    encoder: &sdm_core::FittedFeatureEncoderV2,
    training_fingerprint: String,
) -> Result<TinyMlpPayload, String> {
    config.validate()?;
    if train.is_empty() {
        return Err("empty training set".into());
    }
    if dim == 0 {
        return Err("zero dimension".into());
    }
    let mut params = TinyMlpParams::init(dim, config.hidden_width, config.seed);
    let h = config.hidden_width;
    for _epoch in 0..config.epochs {
        // Deterministic order: seeded shuffle per epoch (Fisher-Yates with XorShift).
        let mut order: Vec<usize> = (0..train.len()).collect();
        let mut rng = XorShift64::new(config.seed.wrapping_add(_epoch as u64));
        for i in (1..order.len()).rev() {
            let j = (rng.next_u64() as usize) % (i + 1);
            order.swap(i, j);
        }
        for &idx in &order {
            let ex = &train[idx];
            let (gw1, gb1, gw2, gb2, gans_w, gans_b, _) = params.gradients(
                &ex.context,
                &ex.candidates,
                ex.target,
                config.lambda_answerability,
            );
            // SGD with L2 + grad clip + finite checks (descent: w -= lr*(g + l2*w)).
            let clip = 10.0;
            let apply = |w: &mut f64, g: f64| {
                let mut gg = g;
                if !gg.is_finite() {
                    gg = 0.0;
                }
                gg = gg.clamp(-clip, clip);
                *w -= config.learning_rate * (gg + config.l2 * *w);
                if !w.is_finite() {
                    *w = 0.0;
                }
                *w = w.clamp(-1_000_000.0, 1_000_000.0);
            };
            for (w, g) in params.w1.iter_mut().zip(gw1) {
                apply(w, g);
            }
            for (w, g) in params.b1.iter_mut().zip(gb1) {
                apply(w, g);
            }
            for (w, g) in params.w2.iter_mut().zip(gw2) {
                apply(w, g);
            }
            apply(&mut params.b2, gb2);
            for (w, g) in params.ans_weights.iter_mut().zip(gans_w) {
                apply(w, g);
            }
            apply(&mut params.ans_bias, gans_b);
        }
    }
    Ok(TinyMlpPayload {
        task: "choice".into(),
        encoder: encoder.clone(),
        hidden_width: h,
        activation: TINYMLP_ACTIVATION.into(),
        w1: params.w1,
        b1: params.b1,
        w2: params.w2,
        b2: params.b2,
        answerability_weights: params.ans_weights,
        answerability_bias: params.ans_bias,
        training_fingerprint,
        seed: config.seed,
    })
}

/// Finite-difference gradient check for both heads (used in tests + CI).
/// Returns max absolute difference between analytic and numeric grads.
pub fn finite_diff_error(dim: usize, hidden: usize, seed: u64, lambda: f64) -> Result<f64, String> {
    let params = TinyMlpParams::init(dim, hidden, seed);
    // Small deterministic example.
    let context: Vec<f64> = (0..dim).map(|i| 0.1 * ((i % 3) as f64 - 1.0)).collect();
    let cands: Vec<Vec<f64>> = (0..2)
        .map(|k| {
            (0..dim)
                .map(|i| 0.1 * (((i + k) % 3) as f64 - 1.0))
                .collect()
        })
        .collect();
    let target = Some(1);
    let (gw1, gb1, gw2, gb2, gans_w, gans_b, _) =
        params.gradients(&context, &cands, target, lambda);
    let eps = 1e-5;
    let loss_at = |p: &TinyMlpParams| {
        // Recompute loss directly for numeric diff.
        let (scores, _, a) = forward(p, &context, &cands);
        let y_ans = 1.0;
        let a_c = a.clamp(1e-15, 1.0 - 1e-15);
        let la = -y_ans * a_c.ln() - (1.0 - y_ans) * (1.0 - a_c).ln();
        let max_s = scores.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        let exps: Vec<f64> = scores.iter().map(|s| (s - max_s).exp()).collect();
        let sum: f64 = exps.iter().sum();
        let lc = -(exps[1] / sum).clamp(1e-15, 1.0).ln();
        la + lambda * lc
    };
    let mut max_err: f64 = 0.0;
    // Numeric check for w1[0..5].
    for (k, gw) in gw1.iter().enumerate().take(5.min(params.w1.len())) {
        let mut pp = params.clone();
        let mut mm = params.clone();
        pp.w1[k] += eps;
        mm.w1[k] -= eps;
        let numeric = (loss_at(&pp) - loss_at(&mm)) / (2.0 * eps);
        max_err = max_err.max((numeric - *gw).abs());
    }
    for j in 0..hidden.min(5) {
        let mut pp = params.clone();
        let mut mm = params.clone();
        pp.b1[j] += eps;
        mm.b1[j] -= eps;
        let numeric = (loss_at(&pp) - loss_at(&mm)) / (2.0 * eps);
        max_err = max_err.max((numeric - gb1[j]).abs());
        let mut pp2 = params.clone();
        let mut mm2 = params.clone();
        pp2.w2[j] += eps;
        mm2.w2[j] -= eps;
        let numeric2 = (loss_at(&pp2) - loss_at(&mm2)) / (2.0 * eps);
        max_err = max_err.max((numeric2 - gw2[j]).abs());
    }
    {
        let mut pp = params.clone();
        let mut mm = params.clone();
        pp.b2 += eps;
        mm.b2 -= eps;
        let numeric = (loss_at(&pp) - loss_at(&mm)) / (2.0 * eps);
        max_err = max_err.max((numeric - gb2).abs());
    }
    for (k, gw) in gans_w
        .iter()
        .enumerate()
        .take(5.min(params.ans_weights.len()))
    {
        let mut pp = params.clone();
        let mut mm = params.clone();
        pp.ans_weights[k] += eps;
        mm.ans_weights[k] -= eps;
        let numeric = (loss_at(&pp) - loss_at(&mm)) / (2.0 * eps);
        max_err = max_err.max((numeric - *gw).abs());
    }
    {
        let mut pp = params.clone();
        let mut mm = params.clone();
        pp.ans_bias += eps;
        mm.ans_bias -= eps;
        let numeric = (loss_at(&pp) - loss_at(&mm)) / (2.0 * eps);
        max_err = max_err.max((numeric - gans_b).abs());
    }
    Ok(max_err)
}

/// M016 bounded-grid training spec. Denies unknown fields; fails closed on
/// out-of-bound grids (>36 configs), non-DEV partitions, or SHA drift.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct M016TrainSpec {
    pub dataset_path: String,
    pub split_path: String,
    pub provenance: Provenance,
    pub expected_dataset_sha256: String,
    pub expected_split_fingerprint: String,
    pub output_dir: String,
    #[serde(default = "default_m016_epochs")]
    pub epochs: usize,
    pub hidden_widths: Vec<usize>,
    pub seeds: Vec<u64>,
    pub learning_rates: Vec<f64>,
    pub l2_values: Vec<f64>,
    #[serde(default = "default_m016_lambda")]
    pub lambda_answerability: f64,
    /// Optional JSON export of TRAIN/DEV encoded matrices for the isolated
    /// shallow-tree baseline (same vectors, audited equivalence).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub export_features_path: Option<String>,
}

fn default_m016_epochs() -> usize {
    20
}

fn default_m016_lambda() -> f64 {
    1.0
}

/// Per-candidate DEV metrics for one trained configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct M016CandidateReport {
    pub hidden_width: usize,
    pub seed: u64,
    pub learning_rate: f64,
    pub l2: f64,
    pub epochs: usize,
    pub parameter_count: usize,
    pub dev_n: usize,
    pub dev_answerable: usize,
    pub dev_no_answer: usize,
    pub dev_conditional_accuracy: f64,
    pub dev_conditional_nll: f64,
    pub dev_conditional_brier: f64,
    pub dev_answerability_auroc: f64,
    pub dev_answerability_ap: f64,
    pub dev_answerability_ece: f64,
    pub dev_threshold: f64,
    pub dev_answerable_final_accuracy: f64,
    pub dev_false_abstention_rate: f64,
    pub dev_coverage: f64,
    pub dev_no_answer_recall: f64,
    pub dev_false_positive_rate: f64,
    /// Eval-time ablations (no retraining): zeroed-context / zeroed-candidate
    /// conditional accuracy + always-answer conditional accuracy.
    pub ablation_context_only_conditional_accuracy: f64,
    pub ablation_candidate_only_conditional_accuracy: f64,
    pub ablation_no_head_conditional_accuracy: f64,
    pub per_family_answerable_final_accuracy: BTreeMap<String, f64>,
    pub per_family_support: BTreeMap<String, usize>,
    /// Answerable final accuracy sliced by option count (2..=128 present).
    pub accuracy_by_option_count: BTreeMap<String, f64>,
    pub support_by_option_count: BTreeMap<String, usize>,
    pub train_loss_final: f64,
}

/// Top-level M016 training report (written atomically, no overwrite).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct M016TrainReport {
    pub schema: String,
    pub architecture: String,
    pub partition: String,
    pub dataset_sha256: String,
    pub split_fingerprint: String,
    pub dataset_file_sha256: String,
    pub split_file_sha256: String,
    pub train_rows: usize,
    pub train_groups: usize,
    pub dev_rows: usize,
    pub dev_groups: usize,
    pub grid_size: usize,
    pub selection_objective: String,
    pub selected_index: usize,
    pub selected_artifact_path: String,
    pub selected_artifact_sha256: String,
    pub selected_calibration_sha256: String,
    pub selected_model_id: String,
    pub candidates: Vec<M016CandidateReport>,
    /// Measured on this host: encode+infer ms for fixed option counts.
    pub latency_ms_by_options: BTreeMap<String, f64>,
    pub peak_rss_bytes: Option<u64>,
    pub build_profile: String,
    pub host: String,
    pub source_commit: String,
}

fn m016_sha_hex(bytes: &[u8]) -> String {
    format!("sha256:{:x}", Sha256::digest(bytes))
}

fn m016_atomic_write_new(path: &str, bytes: &[u8]) -> Result<(), ExperimentError> {
    let target = Path::new(path);
    if target.exists() {
        return Err(ExperimentError::Invalid(format!(
            "refusing to overwrite {path}"
        )));
    }
    let parent = target
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    fs::create_dir_all(parent)?;
    let tmp = parent.join(format!(
        ".sdm-m016-{}-{}.tmp",
        std::process::id(),
        Sha256::digest(path.as_bytes())[0]
    ));
    use std::io::Write;
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&tmp)?;
    file.write_all(bytes)?;
    file.sync_all()?;
    let _: serde_json::Value = serde_json::from_slice(bytes)?;
    fs::hard_link(&tmp, target)?;
    fs::remove_file(tmp)?;
    Ok(())
}

/// Partition examples by split ID lists (fail-closed on missing/extra IDs).
fn m016_partition<'a>(
    examples: &'a [DatasetExample],
    ids: &[String],
    what: &str,
) -> Result<Vec<&'a DatasetExample>, ExperimentError> {
    let by_id: BTreeMap<&str, &DatasetExample> =
        examples.iter().map(|e| (e.case_id.as_str(), e)).collect();
    let mut out = Vec::with_capacity(ids.len());
    for id in ids {
        let e = by_id.get(id.as_str()).ok_or_else(|| {
            ExperimentError::Invalid(format!("split {what} id {id} missing from dataset"))
        })?;
        out.push(*e);
    }
    Ok(out)
}

/// Fit the shared encoder TRAIN-ONLY (same procedure as legacy typed heads).
fn m016_fit_encoder_train_only(
    train: &[&DatasetExample],
) -> Result<sdm_core::FittedFeatureEncoderV2, ExperimentError> {
    let first = train
        .first()
        .and_then(|e| e.typed_rank_features.as_ref())
        .ok_or_else(|| ExperimentError::Invalid("typed task requires train projections".into()))?;
    let mut projections = Vec::new();
    for e in train {
        let b = e
            .typed_rank_features
            .as_ref()
            .ok_or_else(|| ExperimentError::Invalid("typed training projection missing".into()))?;
        if b.schema
            .fingerprint()
            .map_err(|e| ExperimentError::Invalid(e.to_string()))?
            != first
                .schema
                .fingerprint()
                .map_err(|e| ExperimentError::Invalid(e.to_string()))?
        {
            return Err(ExperimentError::Invalid(
                "typed schema drift in train partition".into(),
            ));
        }
        projections.push(b.context.clone());
        projections.extend(b.candidates.values().cloned());
    }
    sdm_core::FittedFeatureEncoderV2::fit(&first.schema, &projections)
        .map_err(|e| ExperimentError::Invalid(e.to_string()))
}

/// Convert dataset rows to trainer examples in sorted-option-ID order (the
/// same order the runtime scores in). Target is the sorted position, or None.
fn m016_to_examples(
    encoder: &sdm_core::FittedFeatureEncoderV2,
    rows: &[&DatasetExample],
) -> Result<Vec<TinyMlpExample>, ExperimentError> {
    let mut out = Vec::with_capacity(rows.len());
    for e in rows {
        let binding = e
            .typed_rank_features
            .as_ref()
            .ok_or_else(|| ExperimentError::Invalid("typed features missing".into()))?;
        let sdm_core::DecisionSpec::Choice { options, .. } = &e.request.spec else {
            return Err(ExperimentError::Invalid(
                "m016 requires Choice requests".into(),
            ));
        };
        if options.len() < 2 || options.len() > 128 {
            return Err(ExperimentError::Invalid(format!(
                "Choice requires 2..=128 options, got {}",
                options.len()
            )));
        }
        let mut ids: Vec<&str> = options.iter().map(|o| o.id.as_str()).collect();
        ids.sort();
        let context = encoder
            .encode(&binding.context)
            .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
        let mut candidates = Vec::with_capacity(ids.len());
        for id in &ids {
            let p = binding.candidates.get(*id).ok_or_else(|| {
                ExperimentError::Invalid("typed option projection missing".into())
            })?;
            candidates.push(
                encoder
                    .encode(p)
                    .map_err(|e| ExperimentError::Invalid(e.to_string()))?,
            );
        }
        let sdm_data::TargetLabel::Choice(target) = &e.label else {
            return Err(ExperimentError::Invalid(
                "m016 requires Choice labels".into(),
            ));
        };
        let target = match target {
            Some(id) => Some(ids.iter().position(|x| x == id).ok_or_else(|| {
                ExperimentError::Invalid("choice target outside permitted option identities".into())
            })?),
            None => None,
        };
        out.push(TinyMlpExample {
            context,
            candidates,
            target,
        });
    }
    Ok(out)
}

fn m016_softmax(scores: &[f64]) -> Vec<f64> {
    let max = scores.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    let exps: Vec<f64> = scores.iter().map(|s| (s - max).exp()).collect();
    let sum: f64 = exps.iter().sum::<f64>().max(1e-300);
    exps.iter().map(|e| e / sum).collect()
}

fn m016_auroc(scores: &[(f64, bool)]) -> f64 {
    let pos = scores.iter().filter(|x| x.1).count() as f64;
    let neg = scores.len() as f64 - pos;
    if pos == 0.0 || neg == 0.0 {
        return 0.5;
    }
    let mut sorted = scores.to_vec();
    sorted.sort_by(|a, b| a.0.total_cmp(&b.0));
    let mut rank_sum = 0.0;
    for (i, s) in sorted.iter().enumerate() {
        if s.1 {
            rank_sum += i as f64 + 1.0;
        }
    }
    (rank_sum - pos * (pos + 1.0) / 2.0) / (pos * neg)
}

fn m016_ap(scores: &[(f64, bool)]) -> f64 {
    let pos = scores.iter().filter(|x| x.1).count();
    if pos == 0 || scores.is_empty() {
        return 0.0;
    }
    let mut sorted = scores.to_vec();
    sorted.sort_by(|a, b| b.0.total_cmp(&a.0));
    let mut hits = 0usize;
    let mut sum_prec = 0.0;
    for (i, s) in sorted.iter().enumerate() {
        if s.1 {
            hits += 1;
            sum_prec += hits as f64 / (i + 1) as f64;
        }
    }
    sum_prec / pos as f64
}

/// Evaluate one trained payload on DEV. Returns the candidate report with a
/// DEV-calibrated threshold (argmax DEV answerable final accuracy, ties to
/// the lower threshold — same tie-break as legacy `select_threshold`).
fn m016_evaluate(
    payload: &TinyMlpPayload,
    params: &TinyMlpParams,
    dev: &[TinyMlpExample],
    dev_rows: &[&DatasetExample],
    config: &TinyMlpConfig,
    train_loss: f64,
) -> M016CandidateReport {
    let n = dev.len();
    let mut cond_correct = 0usize;
    let mut nll = 0.0;
    let mut brier = 0.0;
    let mut n_answerable = 0usize;
    let mut ans_obs: Vec<(f64, bool)> = Vec::with_capacity(n);
    // Per-example cached (scores, probs, answerability).
    let mut cache: Vec<(Vec<f64>, Vec<f64>, f64)> = Vec::with_capacity(n);
    for ex in dev {
        let (scores, _, a) = forward(params, &ex.context, &ex.candidates);
        let probs = m016_softmax(&scores);
        cache.push((scores, probs, a));
        let answerable = ex.target.is_some();
        ans_obs.push((a, answerable));
        if let Some(t) = ex.target {
            n_answerable += 1;
            let best = cache
                .last()
                .unwrap()
                .1
                .iter()
                .enumerate()
                .max_by(|a, b| a.1.total_cmp(b.1).then_with(|| b.0.cmp(&a.0)))
                .map(|x| x.0)
                .unwrap_or(0);
            if best == t {
                cond_correct += 1;
            }
            nll += -cache.last().unwrap().1[t].clamp(1e-15, 1.0).ln();
            for (k, p) in cache.last().unwrap().1.iter().enumerate() {
                let y = if k == t { 1.0 } else { 0.0 };
                brier += (p - y) * (p - y);
            }
        }
    }
    let n_no_answer = n - n_answerable;
    let cond_acc = if n_answerable > 0 {
        cond_correct as f64 / n_answerable as f64
    } else {
        0.0
    };
    let cond_nll = if n_answerable > 0 {
        nll / n_answerable as f64
    } else {
        0.0
    };
    let cond_brier = if n_answerable > 0 {
        brier / n_answerable as f64
    } else {
        0.0
    };
    let auroc = m016_auroc(&ans_obs);
    let ap = m016_ap(&ans_obs);
    // ECE over answerability (10 equal-width bins).
    let mut ece = 0.0;
    for b in 0..10 {
        let lo = b as f64 / 10.0;
        let hi = (b + 1) as f64 / 10.0;
        let mut cnt = 0usize;
        let mut sum_p = 0.0;
        let mut sum_y = 0usize;
        for (p, y) in &ans_obs {
            if *p >= lo && (*p < hi || (b == 9 && *p <= hi)) {
                cnt += 1;
                sum_p += *p;
                if *y {
                    sum_y += 1;
                }
            }
        }
        if cnt > 0 {
            ece += (cnt as f64 / n as f64)
                * ((sum_p / cnt as f64) - (sum_y as f64 / cnt as f64)).abs();
        }
    }
    // Threshold sweep on DEV answerability (balanced accuracy, same policy as
    // legacy `select_threshold`: max 0.5*(TPR+TNR), ties to lower threshold).
    // The threshold is deliberately NOT fit to final ranking accuracy, which
    // admits the degenerate always-answer point; final-action metrics below
    // are reported at this answerability operating point.
    let mut best_t = 0.5;
    let mut best_bal = -1.0f64;
    for i in 0..=100 {
        let t = i as f64 / 100.0;
        let mut tp = 0usize; // answerable + answered
        let mut tn = 0usize; // no-answer + abstained
        for (k, ex) in dev.iter().enumerate() {
            let answered = cache[k].2 >= t;
            match ex.target {
                Some(_) => {
                    if answered {
                        tp += 1;
                    }
                }
                None => {
                    if !answered {
                        tn += 1;
                    }
                }
            }
        }
        let tpr = if n_answerable > 0 {
            tp as f64 / n_answerable as f64
        } else {
            0.0
        };
        let tnr = if n_no_answer > 0 {
            tn as f64 / n_no_answer as f64
        } else {
            0.0
        };
        let bal = 0.5 * (tpr + tnr);
        let better = bal > best_bal + 1e-12 || ((bal - best_bal).abs() <= 1e-12 && t < best_t);
        if better {
            best_bal = bal;
            best_t = t;
        }
    }
    // Final-action metrics at the chosen operating point.
    let mut tp_ans = 0usize;
    let mut fa = 0usize;
    let mut covered = 0usize;
    let mut na_ok = 0usize;
    let mut fp = 0usize;
    for (k, ex) in dev.iter().enumerate() {
        let (_, probs, a) = &cache[k];
        let answered = *a >= best_t;
        match ex.target {
            Some(tgt) => {
                if answered {
                    covered += 1;
                    let best = probs
                        .iter()
                        .enumerate()
                        .max_by(|a, b| a.1.total_cmp(b.1).then_with(|| b.0.cmp(&a.0)))
                        .map(|x| x.0)
                        .unwrap_or(0);
                    if best == tgt {
                        tp_ans += 1;
                    }
                } else {
                    fa += 1;
                }
            }
            None => {
                if answered {
                    fp += 1;
                } else {
                    na_ok += 1;
                }
            }
        }
    }
    let best_stats = (
        if n_answerable > 0 {
            fa as f64 / n_answerable as f64
        } else {
            0.0
        },
        if n_answerable > 0 {
            covered as f64 / n_answerable as f64
        } else {
            0.0
        },
        if n_no_answer > 0 {
            na_ok as f64 / n_no_answer as f64
        } else {
            0.0
        },
        if n_no_answer > 0 {
            fp as f64 / n_no_answer as f64
        } else {
            0.0
        },
        if n_answerable > 0 {
            tp_ans as f64 / n_answerable as f64
        } else {
            0.0
        },
    );
    // Eval-time ablations (no retraining).
    let zero_ctx_acc = m016_ablated_accuracy(params, dev, true, false);
    let zero_cand_acc = m016_ablated_accuracy(params, dev, false, true);
    // Per-family answerable final accuracy at the chosen threshold.
    let mut fam_correct: BTreeMap<String, usize> = BTreeMap::new();
    let mut fam_total: BTreeMap<String, usize> = BTreeMap::new();
    for (k, row) in dev_rows.iter().enumerate() {
        let ex = &dev[k];
        let Some(tgt) = ex.target else { continue };
        let fam = row.family.clone().unwrap_or_else(|| "unknown".into());
        *fam_total.entry(fam.clone()).or_insert(0) += 1;
        let (_, probs, a) = &cache[k];
        if *a >= best_t {
            let best = probs
                .iter()
                .enumerate()
                .max_by(|a, b| a.1.total_cmp(b.1).then_with(|| b.0.cmp(&a.0)))
                .map(|x| x.0)
                .unwrap_or(0);
            if best == tgt {
                *fam_correct.entry(fam).or_insert(0) += 1;
            }
        }
    }
    let mut fam_acc = BTreeMap::new();
    for (fam, total) in &fam_total {
        let c = fam_correct.get(fam).copied().unwrap_or(0);
        fam_acc.insert(fam.clone(), c as f64 / *total as f64);
    }
    // Accuracy by option count (answerable rows, final actions at threshold).
    let mut opt_correct: BTreeMap<usize, usize> = BTreeMap::new();
    let mut opt_total: BTreeMap<usize, usize> = BTreeMap::new();
    for (k, ex) in dev.iter().enumerate() {
        let Some(tgt) = ex.target else { continue };
        let k_opts = ex.candidates.len();
        *opt_total.entry(k_opts).or_insert(0) += 1;
        let (_, probs, a) = &cache[k];
        if *a >= best_t {
            let best = probs
                .iter()
                .enumerate()
                .max_by(|a, b| a.1.total_cmp(b.1).then_with(|| b.0.cmp(&a.0)))
                .map(|x| x.0)
                .unwrap_or(0);
            if best == tgt {
                *opt_correct.entry(k_opts).or_insert(0) += 1;
            }
        }
    }
    let mut acc_by_k = BTreeMap::new();
    let mut sup_by_k = BTreeMap::new();
    for (k, total) in &opt_total {
        let c = opt_correct.get(k).copied().unwrap_or(0);
        acc_by_k.insert(k.to_string(), c as f64 / *total as f64);
        sup_by_k.insert(k.to_string(), *total);
    }
    M016CandidateReport {
        hidden_width: config.hidden_width,
        seed: config.seed,
        learning_rate: config.learning_rate,
        l2: config.l2,
        epochs: config.epochs,
        parameter_count: payload.parameter_count(),
        dev_n: n,
        dev_answerable: n_answerable,
        dev_no_answer: n_no_answer,
        dev_conditional_accuracy: cond_acc,
        dev_conditional_nll: cond_nll,
        dev_conditional_brier: cond_brier,
        dev_answerability_auroc: auroc,
        dev_answerability_ap: ap,
        dev_answerability_ece: ece,
        dev_threshold: best_t,
        dev_answerable_final_accuracy: best_stats.4,
        dev_false_abstention_rate: best_stats.0,
        dev_coverage: best_stats.1,
        dev_no_answer_recall: best_stats.2,
        dev_false_positive_rate: best_stats.3,
        ablation_context_only_conditional_accuracy: zero_cand_acc,
        ablation_candidate_only_conditional_accuracy: zero_ctx_acc,
        ablation_no_head_conditional_accuracy: cond_acc,
        per_family_answerable_final_accuracy: fam_acc,
        per_family_support: fam_total,
        accuracy_by_option_count: acc_by_k,
        support_by_option_count: sup_by_k,
        train_loss_final: train_loss,
    }
}

/// Conditional accuracy with zeroed context or zeroed candidates (control).
fn m016_ablated_accuracy(
    params: &TinyMlpParams,
    dev: &[TinyMlpExample],
    zero_context: bool,
    zero_candidates: bool,
) -> f64 {
    let mut correct = 0usize;
    let mut total = 0usize;
    for ex in dev {
        let Some(t) = ex.target else { continue };
        total += 1;
        let ctx: Vec<f64> = if zero_context {
            vec![0.0; ex.context.len()]
        } else {
            ex.context.clone()
        };
        let cands: Vec<Vec<f64>> = if zero_candidates {
            ex.candidates.iter().map(|c| vec![0.0; c.len()]).collect()
        } else {
            ex.candidates.clone()
        };
        let (scores, _, _) = forward(params, &ctx, &cands);
        let best = scores
            .iter()
            .enumerate()
            .max_by(|a, b| a.1.total_cmp(b.1).then_with(|| b.0.cmp(&a.0)))
            .map(|x| x.0)
            .unwrap_or(0);
        if best == t {
            correct += 1;
        }
    }
    if total == 0 {
        0.0
    } else {
        correct as f64 / total as f64
    }
}

fn m016_train_loss(params: &TinyMlpParams, train: &[TinyMlpExample], lambda: f64) -> f64 {
    if train.is_empty() {
        return 0.0;
    }
    let mut total = 0.0;
    for ex in train {
        let (_, _, _, _, _, _, loss) =
            params.gradients(&ex.context, &ex.candidates, ex.target, lambda);
        total += loss;
    }
    total / train.len() as f64
}

fn m016_peak_rss() -> Option<u64> {
    // Best-effort Linux RSS; None elsewhere (recorded as unavailable).
    #[cfg(target_os = "linux")]
    {
        let text = fs::read_to_string("/proc/self/status").ok()?;
        for line in text.lines() {
            if let Some(rest) = line.strip_prefix("VmHWM:") {
                let kb: u64 = rest.split_whitespace().next()?.parse().ok()?;
                return Some(kb * 1024);
            }
        }
        None
    }
    #[cfg(not(target_os = "linux"))]
    {
        None
    }
}

/// Run the bounded M016 grid, select on DEV, and write artifact + report.
///
/// Predeclared selection: max DEV answerable final-action accuracy, then min
/// DEV conditional NLL, then smaller hidden width, then smaller seed.
pub fn run_m016_train(spec: &M016TrainSpec) -> Result<M016TrainReport, ExperimentError> {
    if spec.hidden_widths.is_empty()
        || spec
            .hidden_widths
            .iter()
            .any(|w| !TINYMLP_HIDDEN_WIDTHS.contains(w))
    {
        return Err(ExperimentError::Invalid(
            "hidden_widths must be a non-empty subset of [32, 64]".into(),
        ));
    }
    if spec.seeds.is_empty() || spec.seeds.len() > 3 {
        return Err(ExperimentError::Invalid("seeds must number 1..=3".into()));
    }
    if spec.learning_rates.is_empty() || spec.learning_rates.len() > 3 {
        return Err(ExperimentError::Invalid(
            "learning_rates must number 1..=3".into(),
        ));
    }
    if spec.l2_values.is_empty() || spec.l2_values.len() > 2 {
        return Err(ExperimentError::Invalid(
            "l2_values must number 1..=2".into(),
        ));
    }
    let grid_size = spec.hidden_widths.len()
        * spec.seeds.len()
        * spec.learning_rates.len()
        * spec.l2_values.len();
    if grid_size > 36 {
        return Err(ExperimentError::Invalid(format!(
            "grid size {grid_size} exceeds 36-config bound"
        )));
    }
    if spec.epochs == 0 || spec.epochs > 500 {
        return Err(ExperimentError::Invalid("epochs must be 1..=500".into()));
    }
    for lr in &spec.learning_rates {
        if !lr.is_finite() || *lr <= 0.0 || *lr > 1.0 {
            return Err(ExperimentError::Invalid(
                "learning rates must be in (0,1]".into(),
            ));
        }
    }
    // Load + validate dataset/split read-only.
    let mut raw = Vec::new();
    fs::File::open(&spec.dataset_path)?
        .take((sdm_data::MAX_DATASET_BYTES + 1) as u64)
        .read_to_end(&mut raw)?;
    let bundle: serde_json::Value = serde_json::from_slice(&raw)?;
    let provenance: Provenance = serde_json::from_value(bundle["provenance"].clone())?;
    if provenance != spec.provenance {
        return Err(ExperimentError::Invalid(
            "config provenance differs from dataset".into(),
        ));
    }
    let examples: Vec<DatasetExample> = serde_json::from_value(bundle["examples"].clone())?;
    let dataset_sha = validate_dataset(&examples, &provenance)
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    if dataset_sha != spec.expected_dataset_sha256 {
        return Err(ExperimentError::Invalid(format!(
            "dataset SHA mismatch: expected {} got {dataset_sha}",
            spec.expected_dataset_sha256
        )));
    }
    let mut split_raw = Vec::new();
    fs::File::open(&spec.split_path)?
        .take((crate::MAX_CONFIG_BYTES + 1) as u64)
        .read_to_end(&mut split_raw)?;
    let split: SplitManifest = serde_json::from_slice(&split_raw)?;
    validate_split(&examples, &split, &dataset_sha)
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    if split.fingerprint != spec.expected_split_fingerprint {
        return Err(ExperimentError::Invalid(format!(
            "split fingerprint mismatch: expected {} got {}",
            spec.expected_split_fingerprint, split.fingerprint
        )));
    }
    if !split.test.is_empty() {
        return Err(ExperimentError::Invalid(
            "m016 training requires empty test partition (train-dev-only)".into(),
        ));
    }
    let train_rows = m016_partition(&examples, &split.train, "train")?;
    let dev_rows = m016_partition(&examples, &split.dev, "dev")?;
    for e in train_rows.iter().chain(dev_rows.iter()) {
        if e.typed_rank_features.is_none() {
            return Err(ExperimentError::Invalid(
                "dataset must contain typed semantic features".into(),
            ));
        }
        if !matches!(&e.label, sdm_data::TargetLabel::Choice(_)) {
            return Err(ExperimentError::Invalid(
                "m016 requires Choice labels".into(),
            ));
        }
    }
    // Fit encoder TRAIN-only, then convert both partitions.
    let encoder = m016_fit_encoder_train_only(&train_rows)?;
    let dim = encoder
        .dimension()
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    let train_ex = m016_to_examples(&encoder, &train_rows)?;
    let dev_ex = m016_to_examples(&encoder, &dev_rows)?;
    let train_id = m016_sha_hex(
        &serde_json::to_vec(&train_rows).map_err(|e| ExperimentError::Invalid(e.to_string()))?,
    );
    let dev_fp = m016_sha_hex(
        &serde_json::to_vec(&dev_rows).map_err(|e| ExperimentError::Invalid(e.to_string()))?,
    );

    // Optional feature export for the isolated tree baseline (same vectors).
    if let Some(path) = &spec.export_features_path {
        let export = serde_json::json!({
            "schema": "sdm-m016-features-v1",
            "dimension": dim,
            "encoder_fingerprint": encoder.fingerprint,
            "train": train_ex.iter().zip(train_rows.iter()).map(|(x, r)| serde_json::json!({
                "case_id": r.case_id, "family": r.family, "leakage_group": r.leakage_group,
                "pair_id": r.counterfactual_pair, "context": x.context,
                "candidates": x.candidates, "target": x.target,
            })).collect::<Vec<_>>(),
            "dev": dev_ex.iter().zip(dev_rows.iter()).map(|(x, r)| serde_json::json!({
                "case_id": r.case_id, "family": r.family, "leakage_group": r.leakage_group,
                "pair_id": r.counterfactual_pair, "context": x.context,
                "candidates": x.candidates, "target": x.target,
            })).collect::<Vec<_>>(),
        });
        m016_atomic_write_new(
            path,
            &serde_json::to_vec_pretty(&export)
                .map_err(|e| ExperimentError::Invalid(e.to_string()))?,
        )?;
    }

    // Bounded grid.
    let mut candidates: Vec<(M016CandidateReport, TinyMlpPayload, TinyMlpParams)> = Vec::new();
    for w in &spec.hidden_widths {
        for seed in &spec.seeds {
            for lr in &spec.learning_rates {
                for l2 in &spec.l2_values {
                    let config = TinyMlpConfig {
                        hidden_width: *w,
                        learning_rate: *lr,
                        l2: *l2,
                        epochs: spec.epochs,
                        seed: *seed,
                        lambda_answerability: spec.lambda_answerability,
                    };
                    let payload =
                        train_tinymlp(&train_ex, dim, &config, &encoder, train_id.clone())
                            .map_err(ExperimentError::Invalid)?;
                    let params = TinyMlpParams {
                        hidden: *w,
                        dim,
                        w1: payload.w1.clone(),
                        b1: payload.b1.clone(),
                        w2: payload.w2.clone(),
                        b2: payload.b2,
                        ans_weights: payload.answerability_weights.clone(),
                        ans_bias: payload.answerability_bias,
                    };
                    let loss = m016_train_loss(&params, &train_ex, spec.lambda_answerability);
                    let report =
                        m016_evaluate(&payload, &params, &dev_ex, &dev_rows, &config, loss);
                    candidates.push((report, payload, params));
                }
            }
        }
    }
    // Predeclared selection: max DEV answerable final-action accuracy, then
    // smaller (hidden width, seed), then min DEV conditional NLL, then smaller
    // (learning rate, l2). Discrete criteria precede NLL so selection is
    // robust to last-ulp floating-point variation across hosts; tolerances
    // (1e-9) sit far below one DEV row's metric quantum (~1/480).
    let mut best = 0usize;
    for (i, (r, _, _)) in candidates.iter().enumerate() {
        let b = &candidates[best].0;
        let d_final = r.dev_answerable_final_accuracy - b.dev_answerable_final_accuracy;
        let d_nll = r.dev_conditional_nll - b.dev_conditional_nll;
        let better = d_final > 1e-9
            || (d_final.abs() <= 1e-9 && (r.hidden_width, r.seed) < (b.hidden_width, b.seed))
            || (d_final.abs() <= 1e-9
                && (r.hidden_width, r.seed) == (b.hidden_width, b.seed)
                && d_nll < -1e-9)
            || (d_final.abs() <= 1e-9
                && (r.hidden_width, r.seed) == (b.hidden_width, b.seed)
                && d_nll.abs() <= 1e-9
                && (r.learning_rate, r.l2) < (b.learning_rate, b.l2));
        if better {
            best = i;
        }
    }
    let (best_report, best_payload, _) = &candidates[best];
    // Wrap the winner in a bounded v2 envelope (DEV-calibrated threshold).
    let envelope = sdm_runtime::ArtifactEnvelopeV2::for_typed_choice_tinymlp(
        &encoder,
        (*best_payload).clone(),
        best_report.dev_threshold,
        dev_fp.clone(),
        format!("tinymlp-choice:{train_id}"),
        sdm_core::MAX_OPTIONS,
    )
    .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    // Verify dispatch + inference parity through the real runtime before writing.
    let artifact_bytes =
        serde_json::to_vec(&envelope).map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    let loaded = sdm_runtime::load_artifact(&artifact_bytes)
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    let sdm_runtime::LoadedArtifact::TinyMlpChoiceV2(runtime) = loaded else {
        return Err(ExperimentError::Invalid(
            "tinymlp artifact did not dispatch to TinyMLP runtime".into(),
        ));
    };
    // Spot parity: first DEV row through runtime vs direct forward. The
    // runtime returns logits in request option order; the trainer scores in
    // sorted-ID order, so map positions before comparing.
    if let (Some(first_row), Some(first_ex)) = (dev_rows.first(), dev_ex.first()) {
        let binding = first_row
            .typed_rank_features
            .as_ref()
            .ok_or_else(|| ExperimentError::Invalid("typed features missing".into()))?;
        let rt_logits = runtime
            .choice_logits(&first_row.request, binding)
            .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
        let (scores, _, _) = forward(&candidates[best].2, &first_ex.context, &first_ex.candidates);
        let sdm_core::DecisionSpec::Choice { options, .. } = &first_row.request.spec else {
            return Err(ExperimentError::Invalid(
                "m016 requires Choice requests".into(),
            ));
        };
        let mut sorted_ids: Vec<&str> = options.iter().map(|o| o.id.as_str()).collect();
        sorted_ids.sort();
        if rt_logits.len() != scores.len() || rt_logits.len() != sorted_ids.len() {
            return Err(ExperimentError::Invalid(
                "train/runtime logit length mismatch".into(),
            ));
        }
        for (i, opt) in options.iter().enumerate() {
            let sorted_pos = sorted_ids
                .iter()
                .position(|id| *id == opt.id)
                .ok_or_else(|| {
                    ExperimentError::Invalid("request option missing from sorted ids".into())
                })?;
            if (rt_logits[i] - scores[sorted_pos]).abs() > 1e-9 {
                return Err(ExperimentError::Invalid(format!(
                    "train/runtime logit parity breach: {} vs {}",
                    rt_logits[i], scores[sorted_pos]
                )));
            }
        }
    }
    // Latency probe on this host (same artifact bytes, fixed option counts).
    let mut latency_ms_by_options: BTreeMap<String, f64> = BTreeMap::new();
    if let Some(first_row) = dev_rows.first() {
        let binding = first_row
            .typed_rank_features
            .as_ref()
            .ok_or_else(|| ExperimentError::Invalid("typed features missing".into()))?;
        for k in [2usize, 8, 16, 64, 128] {
            // Repeat the first row's projections to k options (timing only).
            let mut feat = (*binding).clone();
            let base: Vec<(String, sdm_core::FeatureProjectionV2)> = feat
                .candidates
                .iter()
                .map(|(a, b)| (a.clone(), b.clone()))
                .collect();
            feat.candidates.clear();
            for i in 0..k {
                let (id, proj) = &base[i % base.len()];
                feat.candidates
                    .insert(format!("{id}-p{i:03}"), (*proj).clone());
            }
            let mut req = first_row.request.clone();
            if let sdm_core::DecisionSpec::Choice { options, .. } = &mut req.spec {
                let base_opts = options.clone();
                options.clear();
                for i in 0..k {
                    let mut o = base_opts[i % base_opts.len()].clone();
                    o.id = format!("{}-p{i:03}", o.id);
                    options.push(o);
                }
            }
            let reps = 20usize;
            let start = Instant::now();
            for _ in 0..reps {
                let _ = runtime.decide_typed(&req, &feat);
            }
            latency_ms_by_options.insert(
                k.to_string(),
                start.elapsed().as_secs_f64() * 1000.0 / reps as f64,
            );
        }
    }
    let out_dir = Path::new(&spec.output_dir);
    fs::create_dir_all(out_dir)?;
    let (sel_report, _, _) = &candidates[best];
    let artifact_name = format!(
        "tinymlp-h{:02}-seed{:06}.artifact.json",
        sel_report.hidden_width, sel_report.seed
    );
    let artifact_path = out_dir.join(&artifact_name);
    m016_atomic_write_new(
        artifact_path
            .to_str()
            .ok_or_else(|| ExperimentError::Invalid("non-utf8 artifact path".into()))?,
        &artifact_bytes,
    )?;
    let candidate_reports: Vec<M016CandidateReport> =
        candidates.iter().map(|(r, _, _)| r.clone()).collect();
    let host = std::process::Command::new("uname")
        .args(["-a"])
        .output()
        .ok()
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .unwrap_or_else(|| "unknown".into())
        .trim()
        .to_string();
    let source_commit = std::process::Command::new("git")
        .args(["rev-parse", "HEAD"])
        .output()
        .ok()
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .map(|s| s.trim().to_string())
        .unwrap_or_else(|| "unknown".into());
    let train_groups: BTreeSet<&str> = train_rows
        .iter()
        .map(|e| e.leakage_group.as_str())
        .collect();
    let dev_groups: BTreeSet<&str> = dev_rows.iter().map(|e| e.leakage_group.as_str()).collect();
    let report = M016TrainReport {
        schema: "sdm-m016-train-v1".into(),
        architecture: "typed-choice-tinymlp".into(),
        partition: "TRAIN/DEV only".into(),
        dataset_sha256: dataset_sha,
        split_fingerprint: split.fingerprint.clone(),
        dataset_file_sha256: m016_sha_hex(&raw),
        split_file_sha256: m016_sha_hex(&split_raw),
        train_rows: train_rows.len(),
        train_groups: train_groups.len(),
        dev_rows: dev_rows.len(),
        dev_groups: dev_groups.len(),
        grid_size,
        selection_objective: "max DEV answerable final-action accuracy, then smaller (width, seed), then min DEV conditional NLL, then smaller (lr, l2)".into(),
        selected_index: best,
        selected_artifact_path: artifact_path.to_string_lossy().into_owned(),
        selected_artifact_sha256: envelope.tensor_payload_sha256.clone(),
        selected_calibration_sha256: envelope.calibration_sha256.clone(),
        selected_model_id: format!("tinymlp-choice:{train_id}"),
        candidates: candidate_reports,
        latency_ms_by_options,
        peak_rss_bytes: m016_peak_rss(),
        build_profile: if cfg!(debug_assertions) {
            "debug".into()
        } else {
            "release".into()
        },
        host,
        source_commit,
    };
    let report_path = out_dir.join("m016-train-report.json");
    m016_atomic_write_new(
        report_path
            .to_str()
            .ok_or_else(|| ExperimentError::Invalid("non-utf8 report path".into()))?,
        &serde_json::to_vec_pretty(&report).map_err(|e| ExperimentError::Invalid(e.to_string()))?,
    )?;
    Ok(report)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_encoder() -> sdm_core::FittedFeatureEncoderV2 {
        use sdm_core::{
            FeatureField, FeatureProjectionV2, FeatureSchemaField, FeatureSchemaV2, FeatureType,
            FeatureValue,
        };
        let schema = FeatureSchemaV2 {
            version: 2,
            fields: vec![
                FeatureSchemaField {
                    id: "active".into(),
                    value_type: FeatureType::Boolean,
                    required: true,
                    categories: vec![],
                },
                FeatureSchemaField {
                    id: "role".into(),
                    value_type: FeatureType::Category,
                    required: true,
                    categories: vec!["no".into(), "yes".into()],
                },
            ],
        };
        let proj = |active: bool, role: &str| FeatureProjectionV2 {
            schema_version: 2,
            schema_sha256: schema.fingerprint().unwrap(),
            fields: vec![
                FeatureField {
                    id: "active".into(),
                    required: true,
                    value: Some(FeatureValue::Boolean(active)),
                },
                FeatureField {
                    id: "role".into(),
                    required: true,
                    value: Some(FeatureValue::Category(role.into())),
                },
            ],
        };
        sdm_core::FittedFeatureEncoderV2::fit(&schema, &[proj(true, "yes"), proj(true, "no")])
            .unwrap()
    }

    #[test]
    fn tinymlp_finite_diff_matches_analytic() {
        for hidden in [32, 64] {
            let err = finite_diff_error(3, hidden, 16016, 1.0).unwrap();
            assert!(
                err < 1e-6,
                "hidden {hidden}: finite-diff error {err} exceeds 1e-6"
            );
        }
    }

    #[test]
    fn tinymlp_training_is_deterministic() {
        let encoder = test_encoder();
        let dim = encoder.dimension().unwrap();
        let examples: Vec<TinyMlpExample> = (0..8)
            .map(|i| TinyMlpExample {
                context: vec![0.1 * ((i % 3) as f64 - 1.0); dim],
                candidates: vec![
                    vec![0.2 * (((i + 1) % 3) as f64 - 1.0); dim],
                    vec![0.2 * (((i + 2) % 3) as f64 - 1.0); dim],
                ],
                target: if i % 3 == 2 { None } else { Some(i % 2) },
            })
            .collect();
        let config = TinyMlpConfig {
            hidden_width: 32,
            learning_rate: 0.05,
            l2: 0.0,
            epochs: 3,
            seed: 16016,
            lambda_answerability: 1.0,
        };
        let a = train_tinymlp(&examples, dim, &config, &encoder, "sha256:test".into()).unwrap();
        let b = train_tinymlp(&examples, dim, &config, &encoder, "sha256:test".into()).unwrap();
        assert_eq!(a.w1, b.w1);
        assert_eq!(a.w2, b.w2);
        assert_eq!(a.answerability_weights, b.answerability_weights);
        // Different seed diverges (sanity: init differs).
        let config2 = TinyMlpConfig {
            seed: 999,
            ..config.clone()
        };
        let c = train_tinymlp(&examples, dim, &config2, &encoder, "sha256:test".into()).unwrap();
        assert_ne!(a.w1, c.w1);
    }

    #[test]
    fn tinymlp_training_reduces_loss() {
        // Separable answerability problem: loss must strictly decrease.
        let dim = 2;
        let encoder = test_encoder();
        let dim = encoder.dimension().unwrap().max(dim);
        let mut examples = Vec::new();
        for i in 0..16 {
            let answerable = i % 2 == 0;
            examples.push(TinyMlpExample {
                context: vec![if answerable { 1.0 } else { -1.0 }; dim],
                candidates: vec![vec![0.5; dim], vec![-0.5; dim]],
                target: if answerable { Some(0) } else { None },
            });
        }
        let config = TinyMlpConfig {
            hidden_width: 32,
            learning_rate: 0.1,
            l2: 0.0,
            epochs: 20,
            seed: 16016,
            lambda_answerability: 1.0,
        };
        let before = TinyMlpParams::init(dim, 32, 16016);
        let loss_of = |p: &TinyMlpParams| {
            let mut total = 0.0;
            for ex in &examples {
                let (_, _, _, _, _, _, loss) =
                    p.gradients(&ex.context, &ex.candidates, ex.target, 1.0);
                total += loss;
            }
            total / examples.len() as f64
        };
        let l0 = loss_of(&before);
        let payload =
            train_tinymlp(&examples, dim, &config, &encoder, "sha256:test".into()).unwrap();
        let after = TinyMlpParams {
            hidden: 32,
            dim,
            w1: payload.w1,
            b1: payload.b1,
            w2: payload.w2,
            b2: payload.b2,
            ans_weights: payload.answerability_weights,
            ans_bias: payload.answerability_bias,
        };
        let l1 = loss_of(&after);
        assert!(l1 < l0, "training must reduce loss: before {l0} after {l1}");
    }

    #[test]
    fn tinymlp_rejects_bad_config() {
        let bad = TinyMlpConfig {
            hidden_width: 33,
            learning_rate: 0.05,
            l2: 0.0,
            epochs: 3,
            seed: 1,
            lambda_answerability: 1.0,
        };
        assert!(bad.validate().is_err());
        let bad2 = TinyMlpConfig {
            hidden_width: 32,
            learning_rate: 0.0,
            l2: 0.0,
            epochs: 3,
            seed: 1,
            lambda_answerability: 1.0,
        };
        assert!(bad2.validate().is_err());
    }

    #[test]
    fn tinymlp_softmax_stable_under_large_logits() {
        // Large weights must not produce NaN; runtime fails closed on non-finite.
        let encoder = test_encoder();
        let dim = encoder.dimension().unwrap();
        let mut examples = vec![TinyMlpExample {
            context: vec![5.0; dim],
            candidates: vec![vec![5.0; dim], vec![-5.0; dim]],
            target: Some(0),
        }];
        for _ in 0..3 {
            examples.push(examples[0].clone());
        }
        let config = TinyMlpConfig {
            hidden_width: 32,
            learning_rate: 0.01,
            l2: 1e-4,
            epochs: 2,
            seed: 7,
            lambda_answerability: 1.0,
        };
        let payload =
            train_tinymlp(&examples, dim, &config, &encoder, "sha256:test".into()).unwrap();
        assert!(payload.validate_shapes().is_ok());
        assert!(payload.w1.iter().all(|w| w.is_finite()));
    }
}
