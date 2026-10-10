//! Reproducible CPU benchmark for the registered v2 nonlinear Rank engine.
use sdm_core::{DecisionCandidate, DecisionRequest, DecisionSpec, StateField};
use sdm_nonlinear::initialize;
use sdm_runtime::{ArtifactEnvelopeV2, NonlinearRuntime};
use std::time::Instant;

#[cfg(unix)]
fn peak_rss_bytes() -> Option<u64> {
    let mut usage = std::mem::MaybeUninit::<libc::rusage>::zeroed();
    if unsafe { libc::getrusage(libc::RUSAGE_SELF, usage.as_mut_ptr()) } != 0 {
        return None;
    }
    let value = unsafe { usage.assume_init() }.ru_maxrss.max(0) as u64;
    #[cfg(target_os = "macos")]
    {
        Some(value)
    }
    #[cfg(not(target_os = "macos"))]
    {
        Some(value.saturating_mul(1024))
    }
}
#[cfg(not(unix))]
fn peak_rss_bytes() -> Option<u64> {
    None
}

fn percentile(samples: &[u128], numerator: usize, denominator: usize) -> u128 {
    samples[((samples.len() - 1) * numerator / denominator).min(samples.len() - 1)]
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let model = initialize(
        vec![
            "ctx:inspect".into(),
            "ctx:source".into(),
            "cand:read".into(),
            "cand:write".into(),
            "both:inspect".into(),
            "both:source".into(),
        ],
        16,
        20261010,
    )?;
    let envelope = ArtifactEnvelopeV2::for_nonlinear(
        &model,
        "benchmark-pairwise-v2",
        256,
        0.5,
        "MIT",
        "sdm benchmark",
    )?;
    let bytes = serde_json::to_vec(&envelope)?;
    let start = Instant::now();
    let runtime = NonlinearRuntime::from_bytes(&bytes)?;
    let cold_load_micros = start.elapsed().as_micros();
    let mut rows = Vec::new();
    for count in [1usize, 16, 64, 128, 256] {
        let candidates = (0..count)
            .map(|i| DecisionCandidate {
                id: format!("candidate-{i}"),
                label: if i % 2 == 0 { "read" } else { "write" }.into(),
                description: format!(
                    "{} source files",
                    if i % 2 == 0 { "inspect" } else { "modify" }
                ),
            })
            .collect();
        let request = DecisionRequest {
            request_id: format!("bench-{count}"),
            schema_version: 1,
            state: vec![StateField {
                key: "task".into(),
                value: "inspect source".into(),
            }],
            spec: DecisionSpec::Rank {
                instruction: "rank candidates".into(),
                candidates,
                multi_relevance: true,
            },
        };
        let mut samples = Vec::with_capacity(500);
        for _ in 0..500 {
            let started = Instant::now();
            runtime.decide(&request)?;
            samples.push(started.elapsed().as_micros());
        }
        samples.sort_unstable();
        rows.push(serde_json::json!({"candidate_count":count,"samples":samples.len(),"p50_micros":percentile(&samples,50,100),"p95_micros":percentile(&samples,95,100)}));
    }
    let rejected = NonlinearRuntime::from_bytes(b"invalid").is_err();
    println!(
        "{}",
        serde_json::to_string_pretty(
            &serde_json::json!({"architecture":sdm_nonlinear::ARCHITECTURE,"model_sha256":model.digest()? ,"artifact_sha256":runtime.digest(),"artifact_bytes":bytes.len(),"cold_load_micros":cold_load_micros,"peak_rss_bytes":peak_rss_bytes(),"invalid_artifact_rejected":rejected,"rank_latency":rows})
        )?
    );
    Ok(())
}
