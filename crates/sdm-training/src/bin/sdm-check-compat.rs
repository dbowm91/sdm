use sdm_core::{DecisionAnswer, DecisionRequest, DecisionResponse, DecisionStatus};
use sdm_runtime::{LinearArtifact, Runtime};
use std::{env, fs};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = env::args().skip(1);
    let fixtures = args
        .next()
        .unwrap_or_else(|| "fixtures/codegg-compatibility-v1.jsonl".into());
    let artifact = args
        .next()
        .ok_or("usage: sdm-check-compat <fixture.jsonl> <artifact.json>")?;
    let bytes = fs::read(artifact)?;
    let _: LinearArtifact = serde_json::from_slice(&bytes)?;
    let runtime = Runtime::from_bytes(&bytes)?;
    let mut total = 0usize;
    let mut executed = 0usize;
    for (i, line) in fs::read(fixtures)?
        .split(|b| *b == b'\n')
        .filter(|l| !l.is_empty())
        .enumerate()
    {
        let row: serde_json::Value = serde_json::from_slice(line)?;
        if row["fixture_schema_version"] != 1 {
            return Err(format!("fixture line {}: schema mismatch", i + 1).into());
        }
        let request: DecisionRequest = serde_json::from_value(row["request"].clone())?;
        let valid = row
            .get("expect_request_valid")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);
        if valid {
            request.validate()?;
        } else if request.validate().is_ok() {
            return Err(format!("fixture line {}: expected invalid request", i + 1).into());
        }
        let expected: Option<DecisionResponse> = if row["response"].is_null() {
            None
        } else {
            Some(serde_json::from_value(row["response"].clone())?)
        };
        if let Some(response) = &expected {
            response.validate_for(&request)?;
        }
        if valid {
            let actual = runtime.decide(&request)?;
            actual.validate_for(&request)?;
            if row.get("source_case_id").is_some_and(|v| !v.is_null()) {
                let expected = expected
                    .as_ref()
                    .ok_or("source compatibility fixture lacks expected response")?;
                if !matches!(
                    actual.status,
                    DecisionStatus::Answered | DecisionStatus::Abstained { .. }
                ) {
                    return Err(format!(
                        "fixture line {}: runtime returned a non-decision status {:?}",
                        i + 1,
                        actual.status
                    )
                    .into());
                }
                if let (
                    Some(DecisionAnswer::Rank {
                        candidates: actual_candidates,
                    }),
                    Some(DecisionAnswer::Rank {
                        candidates: expected_candidates,
                    }),
                ) = (&actual.answer, &expected.answer)
                {
                    if actual_candidates
                        .iter()
                        .map(|c| c.candidate_id.as_str())
                        .collect::<std::collections::BTreeSet<_>>()
                        != expected_candidates
                            .iter()
                            .map(|c| c.candidate_id.as_str())
                            .collect::<std::collections::BTreeSet<_>>()
                    {
                        return Err(format!(
                            "fixture line {}: runtime candidate identity set differs",
                            i + 1
                        )
                        .into());
                    }
                }
                if actual.provenance.backend != "sdm-local"
                    || actual.provenance.runtime_version.as_deref()
                        != Some(sdm_runtime::RUNTIME_VERSION)
                    || actual.provenance.model.as_deref() != Some(runtime.digest())
                {
                    return Err(format!(
                        "fixture line {}: runtime provenance is incomplete or inconsistent",
                        i + 1
                    )
                    .into());
                }
            }
            executed += 1;
        }
        total += 1;
    }
    println!(
        "validated {total} frozen CodeGG decision fixtures ({executed} runtime executions) with runtime {} ({})",
        sdm_runtime::RUNTIME_VERSION,
        runtime.digest()
    );
    Ok(())
}
