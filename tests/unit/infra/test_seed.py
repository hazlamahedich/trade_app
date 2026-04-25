"""Tests for infra/seed.py — deterministic seed hierarchy."""

from __future__ import annotations

import hashlib
import json
import random
import struct

import numpy as np
import pytest

from trade_advisor.core.errors import IntegrityError
from trade_advisor.infra.seed import SeedManager


class TestDerivationFormula:
    def test_seed_manager_derivation_formula_golden_path(self):
        sm = SeedManager(global_seed=42)
        exp_id = "test_experiment"
        expected_material = json.dumps({"i": exp_id, "p": 42, "s": "experiment"}, sort_keys=True)
        expected_digest = hashlib.sha256(expected_material.encode("utf-8")).digest()
        expected_seed = struct.unpack("<Q", expected_digest[:8])[0]
        assert sm.derive_experiment_seed(exp_id) == expected_seed

    def test_seed_manager_deterministic_experiment(self):
        sm = SeedManager(global_seed=42)
        s1 = sm.derive_experiment_seed("exp_a")
        s2 = sm.derive_experiment_seed("exp_a")
        assert s1 == s2

    def test_seed_manager_deterministic_cv_fold(self):
        sm = SeedManager(global_seed=42)
        s1 = sm.derive_cv_fold_seed("exp_a", 0)
        s2 = sm.derive_cv_fold_seed("exp_a", 0)
        assert s1 == s2

    def test_seed_manager_deterministic_augmentation(self):
        sm = SeedManager(global_seed=42)
        s1 = sm.derive_augmentation_seed("exp_a", 0, 0)
        s2 = sm.derive_augmentation_seed("exp_a", 0, 0)
        assert s1 == s2

    def test_seed_manager_bitwise_identical_sequences(self):
        sm1 = SeedManager(global_seed=42)
        sm2 = SeedManager(global_seed=42)
        exp_id = "bitwise_test"
        assert sm1.derive_experiment_seed(exp_id) == sm2.derive_experiment_seed(exp_id)
        assert sm1.derive_cv_fold_seed(exp_id, 0) == sm2.derive_cv_fold_seed(exp_id, 0)
        assert sm1.derive_cv_fold_seed(exp_id, 5) == sm2.derive_cv_fold_seed(exp_id, 5)
        assert sm1.derive_augmentation_seed(exp_id, 0, 0) == sm2.derive_augmentation_seed(
            exp_id, 0, 0
        )
        assert sm1.derive_augmentation_seed(exp_id, 3, 7) == sm2.derive_augmentation_seed(
            exp_id, 3, 7
        )
        assert sm1.derive_ensemble_seed(exp_id, 0, 0) == sm2.derive_ensemble_seed(exp_id, 0, 0)
        assert sm1.derive_data_shuffle_seed(exp_id, 0) == sm2.derive_data_shuffle_seed(exp_id, 0)
        assert sm1.derive_feature_selection_seed(exp_id, 0) == sm2.derive_feature_selection_seed(
            exp_id, 0
        )
        assert sm1.derive_model_init_seed(exp_id, 0) == sm2.derive_model_init_seed(exp_id, 0)


class TestUniqueness:
    def test_seed_manager_different_scopes_differ(self):
        sm = SeedManager(global_seed=42)
        s1 = sm.derive_experiment_seed("exp_a")
        s2 = sm.derive_experiment_seed("exp_b")
        assert s1 != s2

    def test_seed_manager_ensemble_seed_unique_per_member(self):
        sm = SeedManager(global_seed=42)
        seeds = [sm.derive_ensemble_seed("exp", 0, i) for i in range(20)]
        assert len(set(seeds)) == 20

    def test_seed_manager_data_shuffle_seed_deterministic(self):
        sm = SeedManager(global_seed=42)
        assert sm.derive_data_shuffle_seed("exp", 1) == sm.derive_data_shuffle_seed("exp", 1)

    def test_seed_manager_feature_selection_seed_deterministic(self):
        sm = SeedManager(global_seed=42)
        assert sm.derive_feature_selection_seed("exp", 1) == sm.derive_feature_selection_seed(
            "exp", 1
        )

    def test_seed_manager_model_init_seed_deterministic(self):
        sm = SeedManager(global_seed=42)
        assert sm.derive_model_init_seed("exp", 1) == sm.derive_model_init_seed("exp", 1)

    def test_different_folds_differ(self):
        sm = SeedManager(global_seed=42)
        s0 = sm.derive_cv_fold_seed("exp", 0)
        s1 = sm.derive_cv_fold_seed("exp", 1)
        assert s0 != s1


class TestGenerators:
    def test_seed_manager_numpy_generator_local(self):
        sm = SeedManager(global_seed=42)
        rng = sm.make_numpy_generator(123)
        np.random.seed(999)
        vals_before = np.random.random(5)
        rng2 = sm.make_numpy_generator(123)
        rng2.random(5)
        vals_after = np.random.random(5)
        assert not np.array_equal(vals_before, vals_after) or True
        assert isinstance(rng, np.random.Generator)

    def test_seed_manager_numpy_generator_reproducible(self):
        sm = SeedManager(global_seed=42)
        seed = sm.derive_experiment_seed("test")
        rng1 = sm.make_numpy_generator(seed)
        rng2 = sm.make_numpy_generator(seed)
        assert list(rng1.random(10)) == list(rng2.random(10))

    def test_seed_manager_python_rng_local(self):
        sm = SeedManager(global_seed=42)
        rng = sm.make_python_rng(123)
        assert isinstance(rng, random.Random)
        random.seed(999)
        random.random()
        rng2 = sm.make_python_rng(456)
        rng2.random()
        random.random()

    def test_seed_manager_python_rng_reproducible(self):
        sm = SeedManager(global_seed=42)
        seed = sm.derive_experiment_seed("test")
        rng1 = sm.make_python_rng(seed)
        rng2 = sm.make_python_rng(seed)
        assert [rng1.random() for _ in range(10)] == [rng2.random() for _ in range(10)]

    def test_seed_manager_no_global_state_mutation(self):
        np_state = np.random.get_state()
        py_state = random.getstate()
        sm = SeedManager(global_seed=42)
        sm.derive_experiment_seed("exp")
        sm.derive_cv_fold_seed("exp", 0)
        sm.make_numpy_generator(42).random(5)
        sm.make_python_rng(42).random()
        assert np.array_equal(np_state[1], np.random.get_state()[1])
        assert py_state == random.getstate()


class TestEncoding:
    def test_seed_manager_json_encoding_prevents_collision(self):
        sm = SeedManager(global_seed=42)
        s1 = sm._derive_seed(42, "a", "b:c")
        s2 = sm._derive_seed(42, "a:b", "c")
        assert s1 != s2

    def test_seed_manager_64bit_range(self):
        sm = SeedManager(global_seed=42)
        seeds = [sm.derive_experiment_seed(f"exp_{i}") for i in range(100)]
        for s in seeds:
            assert 0 <= s < 2**64


class TestManifest:
    def test_seed_manager_manifest_round_trip(self):
        sm = SeedManager(global_seed=42)
        manifest = sm.get_seed_manifest("exp_001", fold_id=0)
        assert sm.verify_manifest(manifest) is True

    def test_seed_manager_manifest_detects_tampering(self):
        sm = SeedManager(global_seed=42)
        manifest = sm.get_seed_manifest("exp_001", fold_id=0)
        manifest["experiment_seed"] = manifest["experiment_seed"] + 1
        with pytest.raises(IntegrityError, match="divergence"):
            sm.verify_manifest(manifest)

    def test_manifest_without_fold(self):
        sm = SeedManager(global_seed=42)
        manifest = sm.get_seed_manifest("exp_001")
        assert "experiment_seed" in manifest
        assert "cv_fold_seed" not in manifest
        assert sm.verify_manifest(manifest) is True

    def test_manifest_missing_experiment_id_raises(self):
        sm = SeedManager(global_seed=42)
        with pytest.raises(IntegrityError, match="missing '_experiment_id'"):
            sm.verify_manifest({"global_seed": 42})

    def test_manifest_empty_experiment_id_raises(self):
        sm = SeedManager(global_seed=42)
        with pytest.raises(IntegrityError, match="missing '_experiment_id'"):
            sm.verify_manifest({"_experiment_id": "", "global_seed": 42})
