//! Benchmark one frozen Linux-trained M013a Choice cross artifact on each host.
use sdm_core::{DecisionOption, DecisionRequest, DecisionSpec, TypedRankProjectionV2};
use sdm_runtime::{load_artifact, ArtifactEnvelopeV2, LoadedArtifact, TypedTaskRuntime};
use std::{env, fs, time::Instant};

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

fn percentile(samples: &[u128], n: usize, d: usize) -> u128 {
    samples[((samples.len() - 1) * n / d).min(samples.len() - 1)]
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = env::args().skip(1).collect();
    if args.len() != 2 {
        return Err("usage: benchmark_typed_choice <artifact.json> <m013a-choice.json>".into());
    }
    let bytes = fs::read(&args[0])?;
    let started = Instant::now();
    let LoadedArtifact::TypedTaskV2(runtime) = load_artifact(&bytes)? else {
        return Err("artifact did not dispatch as typed task".into());
    };
    let cold_load_micros = started.elapsed().as_micros();
    let envelope: ArtifactEnvelopeV2 = serde_json::from_slice(&bytes)?;
    let payload: serde_json::Value = serde_json::from_slice(&envelope.payload)?;
    if envelope.architecture != "sdm-typed-choice-cross-v1" {
        return Err("unexpected Choice architecture".into());
    }
    let trainable_parameters = payload["weights"].as_array().map_or(0, Vec::len)
        + payload["answerability_weights"]
            .as_array()
            .map_or(0, Vec::len)
        + payload["choice_cross_pairs"].as_array().map_or(0, Vec::len)
        + 2; // choice bias and answerability bias
    let bundle: serde_json::Value = serde_json::from_slice(&fs::read(&args[1])?)?;
    let example = &bundle["examples"][0];
    let base_request: DecisionRequest = serde_json::from_value(example["request"].clone())?;
    let base_features: TypedRankProjectionV2 =
        serde_json::from_value(example["typed_rank_features"].clone())?;
    let sdm_core::DecisionSpec::Choice {
        options: base_options,
        ..
    } = &base_request.spec
    else {
        return Err("fixture row is not Choice".into());
    };
    let mut latencies = Vec::new();
    for count in [2usize, 16, 64, 128] {
        let options = (0..count)
            .map(|i| DecisionOption {
                id: format!("m013a-option-{i:03}"),
                label: format!("Option {i}"),
            })
            .collect::<Vec<_>>();
        let mut request = base_request.clone();
        if let DecisionSpec::Choice { options: items, .. } = &mut request.spec {
            *items = options.clone();
        }
        let mut features = base_features.clone();
        features.candidates.clear();
        for (i, option) in options.iter().enumerate() {
            let source = &base_options[i % base_options.len()].id;
            features
                .candidates
                .insert(option.id.clone(), base_features.candidates[source].clone());
        }
        let mut samples = Vec::with_capacity(500);
        for _ in 0..500 {
            let t = Instant::now();
            runtime.decide_typed(&request, &features)?;
            samples.push(t.elapsed().as_micros());
        }
        samples.sort_unstable();
        latencies.push(serde_json::json!({"candidate_count":count,"samples":samples.len(),"p50_micros":percentile(&samples,50,100),"p95_micros":percentile(&samples,95,100)}));
    }
    let invalid_rejected = TypedTaskRuntime::from_bytes(b"invalid").is_err();
    println!(
        "{}",
        serde_json::to_string_pretty(&serde_json::json!({
            "architecture":envelope.architecture,"model_sha256":envelope.tensor_payload_sha256,
            "artifact_sha256":runtime.digest(),"artifact_bytes":bytes.len(),"trainable_parameters":trainable_parameters,
            "cross_term_count":payload["choice_cross_pairs"].as_array().map_or(0,Vec::len),
            "cold_load_micros":cold_load_micros,"peak_rss_bytes":peak_rss_bytes(),"invalid_artifact_rejected":invalid_rejected,
            "host":{"os":env::consts::OS,"arch":env::consts::ARCH},"latency":latencies
        }))?
    );
    Ok(())
}
