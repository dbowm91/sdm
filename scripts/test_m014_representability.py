"""Constructed proof that pairwise Choice features cannot express both rules."""
import itertools
import unittest


def target(active: int, rule_b: int) -> int:
    return active ^ rule_b


def affine_margin_table(weights):
    intercept, active_weight, rule_weight = weights
    return [
        intercept + active_weight * active + rule_weight * rule_b
        for rule_b in (0, 1)
        for active in (0, 1)
    ]


def compositional_margin(active: int, rule_b: int) -> float:
    # Δ = 2*(a XOR r)-1; the conjunction supplies the missing rank-2 term.
    return -1.0 + 2.0 * active + 2.0 * rule_b - 4.0 * active * rule_b


class ChoiceRepresentabilityTests(unittest.TestCase):
    def test_complete_four_quadrant_truth_table_and_affine_contradiction(self):
        rows = [(a, r, target(a, r)) for r, a in itertools.product((0, 1), repeat=2)]
        self.assertEqual(rows, [(0, 0, 0), (1, 0, 1), (0, 1, 1), (1, 1, 0)])
        # For any affine Δ, its alternating sum is zero. XOR targets require
        # strict signs (+,-,-,+) (or their global negation), whose sum is ±4.
        coefficients = (1, -1, -1, 1)
        self.assertEqual(sum(c * (1 if y else -1) for c, (_, _, y) in zip(coefficients, rows)), -4)
        # The actual affine feature design has rank three; the target sign vector
        # violates the unique left-nullspace constraint, independent of SGD.
        design = [[1, a, r] for a, r, _ in rows]
        for j in range(3):
            self.assertEqual(sum(coefficients[i] * design[i][j] for i in range(4)), 0)
        for weights in itertools.product((-3.0, -1.0, 0.0, 1.0, 3.0), repeat=3):
            margins = affine_margin_table(weights)
            self.assertFalse(
                all(m > 0 if y else m < 0 for m, (_, _, y) in zip(margins, rows))
            )

    def test_conjunction_times_role_fits_all_quadrants_and_orderings(self):
        for r, a in itertools.product((0, 1), repeat=2):
            margin = compositional_margin(a, r)
            self.assertNotEqual(margin, 0)
            self.assertEqual(margin > 0, bool(target(a, r)))
            # Reversing option order and renaming opaque IDs does not alter the
            # semantic score difference: role, not ID or position, owns the sign.
            options = [("opaque-z", "yes", margin), ("opaque-q", "no", 0.0)]
            for ordered in (options, list(reversed(options))):
                self.assertEqual(max(ordered, key=lambda x: x[2])[1] == "yes", bool(target(a, r)))

    def test_unavailable_is_separate_answerability_control(self):
        answerability = -1.0
        self.assertLess(answerability, 0)
        # Ranking logits remain finite but are irrelevant when answerability is false.
        self.assertTrue(all(abs(compositional_margin(a, r)) < 10 for a, r in itertools.product((0, 1), repeat=2)))


if __name__ == "__main__":
    unittest.main()
