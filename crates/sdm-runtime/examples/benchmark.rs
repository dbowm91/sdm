//! Reproducible microbenchmark for a pinned artifact and compatibility request.
use sdm_core::{DecisionCandidate, DecisionRequest, DecisionSpec};
use sdm_runtime::Runtime;
use std::{env, fs, time::Instant};

#[cfg(unix)]
fn peak_rss_bytes() -> Option<u64> {
    // getrusage reports bytes on macOS and KiB on Linux/BSD.
    let mut usage = std::mem::MaybeUninit::<libc::rusage>::zeroed();
    let result = unsafe { libc::getrusage(libc::RUSAGE_SELF, usage.as_mut_ptr()) };
    if result != 0 {
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

fn percentile(sorted: &[u128], numerator: usize, denominator: usize) -> u128 {
    sorted[((sorted.len().saturating_sub(1) * numerator) / denominator).min(sorted.len() - 1)]
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = env::args().skip(1).collect();
    if args.len() != 2 {
        return Err("usage: cargo run -p sdm-runtime --example benchmark -- <rank-request.json> <artifact.json>".into());
    }
    let request: DecisionRequest = serde_json::from_slice(&fs::read(&args[0])?)?;
    let bytes = fs::read(&args[1])?;
    let load_started = Instant::now();
    let runtime = Runtime::from_bytes(&bytes)?;
    let cold_load_micros = load_started.elapsed().as_micros();
    let DecisionSpec::Rank {
        instruction,
        multi_relevance,
        candidates,
    } = request.spec
    else {
        return Err("benchmark input must be Rank".into());
    };
    let base = DecisionRequest {
        request_id: request.request_id,
        schema_version: request.schema_version,
        state: request.state,
        spec: DecisionSpec::Rank {
            instruction,
            multi_relevance,
            candidates,
        },
    };
    let mut rows = Vec::new();
    for count in [16usize, 64, 128, 256] {
        let DecisionSpec::Rank {
            instruction,
            multi_relevance,
            candidates: original,
        } = &base.spec
        else {
            unreachable!()
        };
        let candidates = (0..count)
            .map(|i| {
                let source = &original[i % original.len()];
                DecisionCandidate {
                    id: format!("{}-{i}", source.id),
                    label: source.label.clone(),
                    description: source.description.clone(),
                }
            })
            .collect();
        let request = DecisionRequest {
            request_id: format!("bench-{count}"),
            schema_version: base.schema_version,
            state: base.state.clone(),
            spec: DecisionSpec::Rank {
                instruction: instruction.clone(),
                multi_relevance: *multi_relevance,
                candidates,
            },
        };
        let mut samples = Vec::with_capacity(200);
        for _ in 0..200 {
            let started = Instant::now();
            runtime.decide(&request)?;
            samples.push(started.elapsed().as_micros());
        }
        samples.sort_unstable();
        rows.push(serde_json::json!({"candidate_count":count,"samples":samples.len(),"p50_micros":percentile(&samples,50,100),"p95_micros":percentile(&samples,95,100)}));
    }
    let failure_started = Instant::now();
    let failure_is_rejected = Runtime::from_bytes(b"not-an-artifact").is_err();
    let failure_latency_micros = failure_started.elapsed().as_micros();
    println!(
        "{}",
        serde_json::to_string_pretty(
            &serde_json::json!({"artifact_sha256":runtime.digest(),"artifact_bytes":bytes.len(),"cold_load_micros":cold_load_micros,"warm_peak_rss_bytes":peak_rss_bytes(),"failure_is_rejected":failure_is_rejected,"failure_latency_micros":failure_latency_micros,"rank_latency":rows})
        )?
    );
    Ok(())
}
