"""Unit tests for SUS scoring (evaluation.usability) and Cohen's kappa."""

from __future__ import annotations

import pytest

from curriculum_mapper.evaluation.metrics import cohens_kappa
from curriculum_mapper.evaluation.usability import (
    summarise_likert,
    summarise_sus,
    sus_band,
    sus_score,
)


class TestSUSScore:
    def test_best_case(self):
        # Odd items = 5, even items = 1 → maximum 100.
        assert sus_score([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]) == 100.0

    def test_worst_case(self):
        assert sus_score([1, 5, 1, 5, 1, 5, 1, 5, 1, 5]) == 0.0

    def test_neutral(self):
        assert sus_score([3] * 10) == 50.0

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError):
            sus_score([5, 5, 5])

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError):
            sus_score([6, 1, 5, 1, 5, 1, 5, 1, 5, 1])


class TestSUSBand:
    @pytest.mark.parametrize("score,band", [
        (85, "excellent"), (72, "good"), (60, "OK (marginal)"), (40, "poor"),
    ])
    def test_bands(self, score, band):
        assert sus_band(score) == band


class TestSummarise:
    def test_summary_keys_and_values(self):
        out = summarise_sus([[5, 1, 5, 1, 5, 1, 5, 1, 5, 1], [3] * 10])
        assert out["n"] == 2
        assert out["mean"] == 75.0
        assert out["min"] == 50.0 and out["max"] == 100.0
        assert out["band"] == "good"

    def test_empty(self):
        assert summarise_sus([])["n"] == 0

    def test_likert_means(self):
        assert summarise_likert([[5, 4, 3], [3, 2, 1]]) == [4.0, 3.0, 2.0]


class TestCohensKappa:
    def test_perfect_agreement(self):
        assert cohens_kappa(["AL", "OS", "DS"], ["AL", "OS", "DS"]) == 1.0

    def test_total_disagreement_two_labels(self):
        # Opposite labels with balanced marginals → kappa = -1.
        assert cohens_kappa(["A", "A", "B", "B"], ["B", "B", "A", "A"]) == -1.0

    def test_partial(self):
        k = cohens_kappa(["AL", "OS", "DS", "AL"], ["AL", "OS", "SE", "DS"])
        assert -1.0 <= k <= 1.0

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            cohens_kappa(["A"], ["A", "B"])

    def test_empty(self):
        assert cohens_kappa([], []) == 0.0
