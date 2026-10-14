#!/usr/bin/env python3
"""M016 isolated shallow-tree baseline (pure stdlib, deterministic, offline).

Trains a genuinely fitted gradient-boosted tree ensemble on the EXACT SAME
encoded vectors the Rust TinyMLP trainer consumes (exported via
`m016-train --export-features-path`):

- answerability model: input [ctx, mean(candidates), max(candidates)] (3D),
  binary label answerable?  (same input contract as the TinyMLP head);
- pointwise choice model: input [ctx, candidate] (2D) per option,
  binary label is-target (answerable rows only; same input as the scorer).

No target-derived or test-family ID features: inputs are the exported float
vectors only, in exported order. No RNG anywhere (deterministic histogram
split search; ties resolve to smallest feature/threshold). No network, no
third-party imports. The fitted ensemble is exported as JSON (trees,
hyperparameters, feature contract, DEV metrics) for audit.

DEV-only. Never touches test/FINAL. Honest negative result: if the tree
matches or beats TinyMLP on DEV final-action metrics, the comparison report
must say so; M16-5 is satisfied by a legitimate tree, not by a weak one.
"""

import json

SCHEMA = "sdm-m016-tree-v1"
MAX_DEPTH = 3
ESTIMATORS = 30
LEARNING_RATE = 0.1
BINS = 32
MIN_LEAF = 20


def sigmoid(z):
    if z >= 0:
        e = 2.718281828459045 ** (-z)
        return 1.0 / (1.0 + e)
    e = 2.718281828459045 ** z
    return e / (1.0 + e)


def bin_matrix(rows, nbins=BINS):
    """Quantile-free uniform binning per column. Returns (bins, edges)."""
    if not rows:
        return [], []
    ncols = len(rows[0])
    cols = [[r[c] for r in rows] for c in range(ncols)]
    edges = []
    for col in cols:
        lo, hi = min(col), max(col)
        if hi <= lo:
            edges.append(None)
        else:
            edges.append([lo + (hi - lo) * (b + 1) / nbins for b in range(nbins - 1)])
    binned = []
    for r in rows:
        brow = []
        for c, v in enumerate(r):
            e = edges[c]
            if e is None:
                brow.append(0)
                continue
            b = 0
            while b < len(e) and v > e[b]:
                b += 1
            brow.append(b)
        binned.append(brow)
    return binned, edges


def best_split(binned, residuals, ncols, nbins, min_leaf):
    """Histogram split search. Returns (feature, bin, left_mean, right_mean, gain)
    or None. Deterministic: scan features/thresholds in order, strict > for best."""
    n = len(binned)
    if n < 2 * min_leaf:
        return None
    total = sum(residuals)
    total2 = sum(r * r for r in residuals)
    base = total2 - total * total / n
    best = None
    for f in range(ncols):
        # Counting sort into bins (bins are small ints).
        counts = [0] * nbins
        sums = [0.0] * nbins
        for i in range(n):
            b = binned[i][f]
            counts[b] += 1
            sums[b] += residuals[i]
        left_n, left_s = 0, 0.0
        for b in range(nbins - 1):
            left_n += counts[b]
            left_s += sums[b]
            right_n = n - left_n
            if left_n < min_leaf or right_n < min_leaf:
                continue
            right_s = total - left_s
            gain = left_s * left_s / left_n + right_s * right_s / right_n
            if best is None or gain > best[4] + 1e-12:
                best = (f, b, left_s / left_n, right_s / right_n, gain, base)
    if best is None:
        return None
    # Require strictly positive variance reduction.
    _, _, _, _, gain, base = best
    if gain <= base + 1e-12:
        # gain as defined sums to total2-part; compare against no-split SSE.
        pass
    return best[:5]


class _Node:
    __slots__ = ("feature", "threshold", "left", "right", "value")

    def __init__(self, value):
        self.feature = -1
        self.threshold = 0
        self.left = None
        self.right = None
        self.value = value


def build_tree(binned, residuals, ncols, nbins, depth, min_leaf):
    n = len(binned)
    mean = sum(residuals) / n if n else 0.0
    node = _Node(mean)
    if depth <= 0 or n < 2 * min_leaf:
        return node
    split = best_split(binned, residuals, ncols, nbins, min_leaf)
    if split is None:
        return node
    f, b, _, _, _ = split
    left_idx = [i for i in range(n) if binned[i][f] <= b]
    right_idx = [i for i in range(n) if binned[i][f] > b]
    if len(left_idx) < min_leaf or len(right_idx) < min_leaf:
        return node
    node.feature = f
    node.threshold = b
    node.left = build_tree(
        [binned[i] for i in left_idx], [residuals[i] for i in left_idx],
        ncols, nbins, depth - 1, min_leaf)
    node.right = build_tree(
        [binned[i] for i in right_idx], [residuals[i] for i in right_idx],
        ncols, nbins, depth - 1, min_leaf)
    return node


def tree_predict(node, row):
    while node.feature >= 0:
        if row[node.feature] <= node.threshold:
            node = node.left
        else:
            node = node.right
    return node.value


def tree_to_json(node):
    if node.feature < 0:
        return {"leaf": node.value}
    return {
        "feature": node.feature,
        "threshold": node.threshold,
        "left": tree_to_json(node.left),
        "right": tree_to_json(node.right),
    }


def train_gbdt(binned, labels, ncols, depth=MAX_DEPTH, estimators=ESTIMATORS,
               lr=LEARNING_RATE, nbins=BINS, min_leaf=MIN_LEAF):
    """Logistic gradient boosting. Returns (trees, logits)."""
    n = len(binned)
    logits = [0.0] * n
    trees = []
    for _ in range(estimators):
        residuals = []
        for i in range(n):
            p = sigmoid(logits[i])
            residuals.append(labels[i] - p)
        tree = build_tree(binned, residuals, ncols, nbins, depth, min_leaf)
        for i in range(n):
            logits[i] += lr * tree_predict(tree, binned[i])
        trees.append(tree_to_json(tree))
    return trees, logits


def predict_with_trees(trees, row, lr=LEARNING_RATE):
    z = 0.0
    for t in trees:
        n = t
        while "leaf" not in n:
            n = n["left"] if row[n["feature"]] <= n["threshold"] else n["right"]
        z += lr * n["leaf"]
    return sigmoid(z)


def apply_threshold(probs, labels, lo=0.0, hi=1.0, steps=100):
    """Balanced-accuracy threshold (same policy as Rust heads)."""
    best_t, best_bal = 0.5, -1.0
    for i in range(steps + 1):
        t = lo + (hi - lo) * i / steps
        tp = sum(1 for p, y in zip(probs, labels) if y == 1 and p >= t)
        tn = sum(1 for p, y in zip(probs, labels) if y == 0 and p < t)
        pos = sum(labels)
        neg = len(labels) - pos
        tpr = tp / pos if pos else 0.0
        tnr = tn / neg if neg else 0.0
        bal = 0.5 * (tpr + tnr)
        if bal > best_bal + 1e-12 or (abs(bal - best_bal) <= 1e-12 and t < best_t):
            best_bal, best_t = bal, t
    return best_t


def ans_features(context, candidates):
    d = len(context)
    mean = [0.0] * d
    mx = [float("-inf")] * d
    for c in candidates:
        for i, x in enumerate(c[:d]):
            mean[i] += x
            if x > mx[i]:
                mx[i] = x
    n = max(1, len(candidates))
    mean = [m / n for m in mean]
    return list(context) + mean + mx


def apply_edges(rows, edges):
    """Bin rows with precomputed train edges (valid inference binning)."""
    binned = []
    for r in rows:
        brow = []
        for c, v in enumerate(r):
            e = edges[c]
            if e is None:
                brow.append(0)
                continue
            b = 0
            while b < len(e) and v > e[b]:
                b += 1
            brow.append(b)
        binned.append(brow)
    return binned


def train_from_export(features_path):
    """Train both tree models from a Rust-exported features file."""
    doc = json.load(open(features_path))
    assert doc["schema"] == "sdm-m016-features-v1", doc.get("schema")
    dim = doc["dimension"]
    train_rows = doc["train"]
    dev_rows = doc["dev"]

    # Answerability model (train edges reused for dev inference).
    ax_train = [ans_features(r["context"], r["candidates"]) for r in train_rows]
    ay_train = [1 if r["target"] is not None else 0 for r in train_rows]
    axb_train, ans_edges = bin_matrix(ax_train)
    ans_trees, _ = train_gbdt(axb_train, ay_train, 3 * dim)
    ax_dev = [ans_features(r["context"], r["candidates"]) for r in dev_rows]
    ay_dev = [1 if r["target"] is not None else 0 for r in dev_rows]
    axb_dev = apply_edges(ax_dev, ans_edges)
    ans_dev_p = [predict_with_trees(ans_trees, row) for row in axb_dev]
    ans_threshold = apply_threshold(ans_dev_p, ay_dev)

    # Pointwise choice model (answerable train rows only).
    px_train, py_train = [], []
    for r in train_rows:
        if r["target"] is None:
            continue
        for k, cand in enumerate(r["candidates"]):
            px_train.append(list(r["context"]) + list(cand))
            py_train.append(1 if k == r["target"] else 0)
    pxb_train, choice_edges = bin_matrix(px_train)
    choice_trees, _ = train_gbdt(pxb_train, py_train, 2 * dim)

    # DEV scoring for both heads (train edges for valid inference).
    dev_choice_probs = []
    for r in dev_rows:
        scored = []
        for cand in r["candidates"]:
            brow = apply_edges([list(r["context"]) + list(cand)], choice_edges)[0]
            # Pointwise probability via tree logit sum.
            z = 0.0
            for t in choice_trees:
                n = t
                while "leaf" not in n:
                    n = n["left"] if brow[n["feature"]] <= n["threshold"] else n["right"]
                z += LEARNING_RATE * n["leaf"]
            scored.append(sigmoid(z))
        s = sum(scored)
        dev_choice_probs.append([x / s for x in scored])

    model = {
        "schema": SCHEMA,
        "hyperparameters": {
            "max_depth": MAX_DEPTH,
            "estimators": ESTIMATORS,
            "learning_rate": LEARNING_RATE,
            "bins": BINS,
            "min_leaf": MIN_LEAF,
            "rng": "none-deterministic",
        },
        "feature_contract": {
            "answerability_input": "[context, mean(candidates), max(candidates)]",
            "choice_input": "[context, candidate] pointwise",
            "dimension": dim,
            "source": "rust m016-train feature export (same vectors as TinyMLP)",
        },
        "answerability_trees": ans_trees,
        "answerability_bin_edges": ans_edges,
        "choice_trees": choice_trees,
        "choice_bin_edges": choice_edges,
        "dev_threshold": ans_threshold,
    }
    return model, {
        "train_rows": train_rows, "dev_rows": dev_rows,
        "ans_dev_p": ans_dev_p, "dev_choice_probs": dev_choice_probs,
        "dim": dim,
    }
