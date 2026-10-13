//! M016 TinyMLP trainer (deterministic, bounded, CPU-only).
//!
//! Trains `sdm-typed-choice-tinymlp-v1` (shared tanh scorer + symmetric
//! answerability) on M015 TRAIN/DEV ONLY. No FINAL, no held-out tuning.
//! All randomness is seeded; two replicas with same seed produce identical bytes.

use sdm_runtime::tinymlp::{TinyMlpPayload, TINYMLP_ACTIVATION, TINYMLP_HIDDEN_WIDTHS};

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
        let d = self.dim;
        let n = candidates.len().max(1) as f64;
        let mut mean = vec![0.0; d];
        let mut max = vec![f64::NEG_INFINITY; d];
        let mut argmax: Vec<usize> = vec![0; d];
        for c in candidates {
            for (i, x) in c.iter().enumerate().take(d) {
                mean[i] += *x;
                if *x > max[i] {
                    max[i] = *x;
                    argmax[i] = 0; // simplified: max grad flows to all max contributors equally
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
            // SGD with L2 + grad clip + finite checks.
            let clip = 10.0;
            let apply = |w: &mut f64, g: f64| {
                let mut gg = g;
                if !gg.is_finite() {
                    gg = 0.0;
                }
                gg = gg.clamp(-clip, clip);
                *w += config.learning_rate * (gg - config.l2 * *w);
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
