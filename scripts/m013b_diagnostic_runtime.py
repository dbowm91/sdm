#!/usr/bin/env python3
"""Read-only, deterministic reproduction of the SDM typed-task runtime scoring.

This mirrors `sdm_core::FittedFeatureEncoderV2::encode` and the typed-task
training/inference arithmetic in `crates/sdm-experiment/src/lib.rs` so that
M013b diagnostics can inspect frozen, already-fitted artifacts without retraining
and without touching any held-out M013a test row.

It is a diagnostic reimplementation, not a second model. Every number it emits is
derived from a frozen artifact payload and a frozen fixture. It never fits,
tunes, thresholds or selects anything.

Version: m013b-diagnostic-runtime-v1
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

RUNTIME_VERSION = "m013b-diagnostic-runtime-v1"

BINARY_ARCH = "sdm-typed-task-v1"
CHOICE_CROSS_ARCH = "sdm-typed-choice-cross-v1"
MAX_TEXT_VOCABULARY = 4096


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_artifact(path: Path) -> dict[str, Any]:
    """Decode a frozen artifact envelope into its typed-task payload."""
    envelope = read_json(path)
    if envelope.get("schema_version") != 2:
        raise ValueError(f"unsupported artifact schema_version {envelope.get('schema_version')!r}")
    payload = envelope["payload"]
    calibration = envelope["calibration_payload"]
    if isinstance(payload, list):
        payload = bytes(payload).decode()
    if isinstance(calibration, list):
        calibration = bytes(calibration).decode()
    model = json.loads(payload)
    model["_calibration"] = json.loads(calibration)
    model["_architecture"] = envelope["architecture"]
    model["_artifact_sha256"] = envelope.get("artifact_sha256") or envelope.get("model_sha256")
    model["_tensor_payload_sha256"] = envelope["tensor_payload_sha256"]
    model["_parameter_count"] = envelope["parameter_count"]
    return model


def tokens(text: str) -> set[str]:
    """Match `sdm_core::tokens`: alphanumeric runs, lowercased, non-empty."""
    current: list[str] = []
    out: set[str] = set()
    for character in text:
        if character.isalnum():
            current.append(character)
        elif current:
            out.add("".join(current).lower())
            current = []
    if current:
        out.add("".join(current).lower())
    return out


def unwrap_value(raw: Any) -> Any:
    """Feature values are `{"type": ..., "value": ...}` wrappers in the corpus."""
    if isinstance(raw, dict) and "value" in raw:
        return raw["value"]
    return raw


class FittedEncoder:
    """Read-only view over a frozen `FittedFeatureEncoderV2`."""

    def __init__(self, encoder: Mapping[str, Any]) -> None:
        self.schema = encoder["schema"]
        self.numeric_center = encoder["numeric_center"]
        self.numeric_scale = encoder["numeric_scale"]
        self.text_vocabulary = encoder["text_vocabulary"]
        self.fingerprint = encoder["fingerprint"]
        self._validate()

    def _validate(self) -> None:
        for scale in self.numeric_scale.values():
            if not math.isfinite(scale) or scale <= 0.0:
                raise ValueError("fitted numeric scale must be finite and positive")
        for vocabulary in self.text_vocabulary.values():
            if len(vocabulary) > MAX_TEXT_VOCABULARY:
                raise ValueError("fitted text vocabulary exceeds the runtime bound")
            if any(vocabulary[i] >= vocabulary[i + 1] for i in range(len(vocabulary) - 1)):
                raise ValueError("fitted text vocabulary is not sorted and unique")

    def dimension(self) -> int:
        total = 0
        for field in self.schema["fields"]:
            kind = field["value_type"]
            if kind in ("number", "boolean"):
                total += 1
            elif kind == "category":
                total += len(field["categories"])
            elif kind == "text":
                total += len(self.text_vocabulary.get(field["id"], []))
        return total

    def coordinate_labels(self) -> list[str]:
        """Human-readable name for each encoded coordinate, in canonical order."""
        labels: list[str] = []
        for field in self.schema["fields"]:
            kind = field["value_type"]
            if kind == "number":
                labels.append(f"{field['id']}")
            elif kind == "boolean":
                labels.append(f"{field['id']}=true")
            elif kind == "category":
                labels.extend(f"{field['id']}={category}" for category in field["categories"])
            elif kind == "text":
                labels.extend(f"{field['id']}~{token}" for token in self.text_vocabulary.get(field["id"], []))
        return labels

    def encode(self, projection: Mapping[str, Any]) -> list[float]:
        values = {field["id"]: unwrap_value(field.get("value")) for field in projection["fields"]}
        output: list[float] = []
        for field in self.schema["fields"]:
            raw = values.get(field["id"])
            kind = field["value_type"]
            if kind == "number":
                if raw is None:
                    output.append(0.0)
                    continue
                center = self.numeric_center[field["id"]]
                scale = self.numeric_scale[field["id"]]
                output.append(max(-5.0, min(5.0, (float(raw) / scale) - (center / scale))))
            elif kind == "boolean":
                output.append(1.0 if isinstance(raw, bool) and raw else 0.0)
            elif kind == "category":
                for category in field["categories"]:
                    output.append(1.0 if isinstance(raw, str) and raw == category else 0.0)
            elif kind == "text":
                vocabulary = self.text_vocabulary.get(field["id"], [])
                present = tokens(raw) if isinstance(raw, str) else set()
                output.extend(1.0 if token in present else 0.0 for token in vocabulary)
            else:
                raise ValueError(f"unsupported feature type {kind!r}")
        return output


def field_values(projection: Mapping[str, Any]) -> dict[str, Any]:
    return {field["id"]: unwrap_value(field.get("value")) for field in projection["fields"]}


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    exponential = math.exp(z)
    return exponential / (1.0 + exponential)


def _softmax(values: Sequence[float]) -> list[float]:
    top = max(values)
    exponentials = [math.exp(v - top) for v in values]
    total = sum(exponentials)
    return [e / total for e in exponentials]


def cross_pair_coordinates(encoder: FittedEncoder) -> list[tuple[int, int]]:
    """Mirror `bounded_nontext_cross_pairs`: all non-text coordinate pairs."""
    coordinates: list[int] = []
    offset = 0
    for field in encoder.schema["fields"]:
        kind = field["value_type"]
        if kind == "text":
            width = 0
        elif kind == "category":
            width = len(field["categories"])
        else:
            width = 1
        coordinates.extend(range(offset, offset + width))
        if kind == "text":
            offset += len(encoder.text_vocabulary.get(field["id"], []))
        elif kind == "category":
            offset += len(field["categories"])
        else:
            offset += 1
    if not coordinates or len(coordinates) ** 2 > 4096:
        raise ValueError("declared Choice cross terms exceed the 4096 runtime bound")
    return [(c, o) for c in coordinates for o in coordinates]


def is_cross_architecture(model: Mapping[str, Any]) -> bool:
    return model.get("_architecture") == CHOICE_CROSS_ARCH or "choice_cross_pairs" in model


class TypedTaskScorer:
    """Frozen typed-task scorer: encode, score, threshold. Never fits."""

    def __init__(self, model: Mapping[str, Any]) -> None:
        self.model = model
        self.encoder = FittedEncoder(model["encoder"])
        self.task = model["task"]
        self.weights: list[float] = list(model["weights"])
        self.bias: float = float(model["bias"])
        self.answerability_weights = model.get("answerability_weights")
        self.answerability_bias = model.get("answerability_bias")
        self.threshold = float(model["_calibration"]["threshold"])
        self.cross = is_cross_architecture(model)
        self.dimension = self.encoder.dimension()
        if self.cross:
            self.cross_pairs = [tuple(pair) for pair in model["choice_cross_pairs"]]
        else:
            self.cross_pairs = []
        self._validate_shapes()

    def _validate_shapes(self) -> None:
        expected = (
            self.dimension * 2 + len(self.cross_pairs)
            if self.task == "choice" and self.cross
            else self.dimension * 3
            if self.task == "choice"
            else self.dimension * 2
        )
        if len(self.weights) != expected:
            raise ValueError(f"weight vector length {len(self.weights)} != expected {expected}")
        if not all(math.isfinite(w) for w in self.weights):
            raise ValueError("weight vector contains a non-finite value")
        if self.task == "choice" and (
            self.answerability_weights is None or self.answerability_bias is None
        ):
            raise ValueError("Choice model is missing its answerability head")

    def standalone_vector(self, context: Sequence[float]) -> list[float]:
        vector = list(context)
        width = self.dimension * 3 if self.task == "choice" and not self.cross else self.dimension * 2
        vector.extend([0.0] * (width - len(vector)))
        return vector

    def option_vector(
        self, context: Sequence[float], option: Sequence[float]
    ) -> list[float]:
        vector = list(context) + list(option)
        if self.cross:
            vector.extend(context[c] * option[o] for c, o in self.cross_pairs)
        else:
            vector.extend(c * o for c, o in zip(context, option))
        return vector

    def _dot(self, vector: Sequence[float]) -> float:
        return sum(a * b for a, b in zip(vector, self.weights)) + self.bias

    def answerability(self, context: Sequence[float]) -> float:
        if self.answerability_weights is None:
            raise ValueError("answerability head is unavailable for this task")
        z = (
            sum(a * b for a, b in zip(context, self.answerability_weights))
            + float(self.answerability_bias)
        )
        return _sigmoid(z)

    def score_example(self, example: Mapping[str, Any]) -> dict[str, Any]:
        binding = example["typed_rank_features"]
        context = self.encoder.encode(binding["context"])
        if self.task == "binary":
            p = _sigmoid(self._dot(self.standalone_vector(context)))
            threshold = self.threshold
            return {
                "case_id": example["case_id"],
                "leakage_group": example["leakage_group"],
                "family": example.get("family"),
                "score": p,
                "logit": math.log(max(p, 1e-15) / max(1.0 - p, 1e-15)),
                "answerability_probability": p,
                "abstained": p < threshold,
                "prediction": bool(p >= 0.5),
                "target": example["label"]["value"],
                "context": context,
            }
        options = example["request"]["spec"]["options"]
        answerability = self.answerability(context)
        abstained = answerability < self.threshold
        logits: list[float] = []
        vectors: list[list[float]] = []
        for option in options:
            candidate = binding["candidates"][option["id"]]
            item = self.encoder.encode(candidate)
            vector = self.option_vector(context, item)
            vectors.append(vector)
            logits.append(self._dot(vector))
        probabilities = _softmax(logits)
        best = max(range(len(probabilities)), key=lambda i: (probabilities[i], -i))
        return {
            "case_id": example["case_id"],
            "leakage_group": example["leakage_group"],
            "family": example.get("family"),
            "answerability_probability": answerability,
            "abstained": abstained,
            "raw_logits": logits,
            "raw_probabilities": probabilities,
            "prediction": None if abstained else options[best]["id"],
            "argmax_option_id": options[best]["id"],
            "target": example["label"]["value"],
            "context": context,
            "option_ids": [o["id"] for o in options],
            "option_vectors": vectors,
            "threshold": self.threshold,
        }

    def score_examples(self, examples: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        return [self.score_example(example) for example in examples]


def with_note(example: Mapping[str, Any], note: str) -> dict[str, Any]:
    """Deep copy with only the context `note` text replaced (label preserving)."""
    clone = json.loads(json.dumps(example))
    for field in clone["typed_rank_features"]["context"]["fields"]:
        if field["id"] == "note":
            field["value"]["value"] = note
    return clone


def with_load(example: Mapping[str, Any], load: float) -> dict[str, Any]:
    clone = json.loads(json.dumps(example))
    for field in clone["typed_rank_features"]["context"]["fields"]:
        if field["id"] == "load":
            field["value"]["value"] = load
    return clone


def with_active(example: Mapping[str, Any], active: bool) -> dict[str, Any]:
    clone = json.loads(json.dumps(example))
    for field in clone["typed_rank_features"]["context"]["fields"]:
        if field["id"] == "active":
            field["value"]["value"] = active
    for projection in clone["typed_rank_features"]["candidates"].values():
        for field in projection["fields"]:
            if field["id"] == "active":
                field["value"]["value"] = active
    return clone


def mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None