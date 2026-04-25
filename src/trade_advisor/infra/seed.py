"""Deterministic seed hierarchy for reproducible experiments.

Seed derivation uses **JSON-structured encoding + SHA-256 → uint64**.

Why JSON encoding?
~~~~~~~~~~~~~~~~~~
Colon-delimited encoding (e.g. ``f"{parent}:{scope}:{id}"``) risks injection
collisions when scope IDs contain the delimiter.  JSON with ``sort_keys=True``
produces deterministic, unambiguous output: ``{"p": 42, "s": "exp", "i": 1}``.

Why 64-bit?
~~~~~~~~~~~
``numpy.random.Generator`` accepts ``uint64`` seeds.  A 32-bit seed has
~50 % collision probability at only 65 K seeds (birthday paradox).  64-bit
pushes that to ~4 billion seeds.
"""

from __future__ import annotations

import hashlib
import json
import random
import struct
from dataclasses import dataclass

import numpy as np

from trade_advisor.core.errors import IntegrityError


@dataclass(frozen=True)
class SeedManager:
    """Hierarchical deterministic seed derivation.

    Hierarchy::

        global_seed
          └─ experiment_seed
               └─ cv_fold_seed
                    ├─ augmentation_seed
                    │    ├─ data_shuffle_seed
                    │    ├─ feature_selection_seed
                    │    └─ model_init_seed
                    └─ ensemble_member_seed
    """

    global_seed: int

    @staticmethod
    def _derive_seed(parent_seed: int, scope: str, scope_id: str | int) -> int:
        material = json.dumps({"i": scope_id, "p": parent_seed, "s": scope}, sort_keys=True)
        digest = hashlib.sha256(material.encode("utf-8")).digest()
        result: int = struct.unpack("<Q", digest[:8])[0]
        return result

    def derive_experiment_seed(self, experiment_id: str) -> int:
        return self._derive_seed(self.global_seed, "experiment", experiment_id)

    def derive_cv_fold_seed(self, experiment_id: str, fold_id: int) -> int:
        exp_seed = self.derive_experiment_seed(experiment_id)
        return self._derive_seed(exp_seed, "cv_fold", fold_id)

    def derive_augmentation_seed(self, experiment_id: str, fold_id: int, aug_id: int) -> int:
        fold_seed = self.derive_cv_fold_seed(experiment_id, fold_id)
        return self._derive_seed(fold_seed, "augmentation", aug_id)

    def derive_ensemble_seed(self, experiment_id: str, fold_id: int, member_id: int) -> int:
        fold_seed = self.derive_cv_fold_seed(experiment_id, fold_id)
        return self._derive_seed(fold_seed, "ensemble_member", member_id)

    def derive_data_shuffle_seed(self, experiment_id: str, fold_id: int) -> int:
        fold_seed = self.derive_cv_fold_seed(experiment_id, fold_id)
        return self._derive_seed(fold_seed, "data_shuffle", 0)

    def derive_feature_selection_seed(self, experiment_id: str, fold_id: int) -> int:
        fold_seed = self.derive_cv_fold_seed(experiment_id, fold_id)
        return self._derive_seed(fold_seed, "feature_selection", 0)

    def derive_model_init_seed(self, experiment_id: str, fold_id: int) -> int:
        fold_seed = self.derive_cv_fold_seed(experiment_id, fold_id)
        return self._derive_seed(fold_seed, "model_init", 0)

    def make_numpy_generator(self, seed: int) -> np.random.Generator:
        return np.random.Generator(np.random.PCG64(seed))

    def make_python_rng(self, seed: int) -> random.Random:
        return random.Random(seed)

    def get_seed_manifest(
        self,
        experiment_id: str,
        fold_id: int | None = None,
        *,
        num_aug_samples: int = 3,
    ) -> dict:
        manifest: dict = {
            "_experiment_id": experiment_id,
            "_fold_id": fold_id,
            "global_seed": self.global_seed,
            "experiment_seed": self.derive_experiment_seed(experiment_id),
        }
        if fold_id is not None:
            manifest["cv_fold_seed"] = self.derive_cv_fold_seed(experiment_id, fold_id)
            manifest["augmentation_seeds"] = {
                f"aug_{i}": self.derive_augmentation_seed(experiment_id, fold_id, i)
                for i in range(num_aug_samples)
            }
            manifest["ensemble_seeds"] = {
                f"member_{i}": self.derive_ensemble_seed(experiment_id, fold_id, i)
                for i in range(num_aug_samples)
            }
            manifest["data_shuffle_seed"] = self.derive_data_shuffle_seed(experiment_id, fold_id)
            manifest["feature_selection_seed"] = self.derive_feature_selection_seed(
                experiment_id, fold_id
            )
            manifest["model_init_seed"] = self.derive_model_init_seed(experiment_id, fold_id)
        return manifest

    def verify_manifest(self, manifest: dict) -> bool:
        experiment_id = manifest.get("_experiment_id")
        if not experiment_id:
            raise IntegrityError("Seed manifest missing '_experiment_id'")
        fold_id = manifest.get("_fold_id")
        fresh = self.get_seed_manifest(experiment_id, fold_id)
        stored = {k: v for k, v in manifest.items() if not k.startswith("_")}
        fresh_clean = {k: v for k, v in fresh.items() if not k.startswith("_")}
        if stored != fresh_clean:
            for k in stored:
                if k in fresh_clean and stored[k] != fresh_clean[k]:
                    raise IntegrityError(
                        f"Seed manifest divergence at '{k}': "
                        f"stored={stored[k]}, fresh={fresh_clean[k]}",
                        details={"key": k},
                    )
            raise IntegrityError("Seed manifest structure mismatch")
        return True
