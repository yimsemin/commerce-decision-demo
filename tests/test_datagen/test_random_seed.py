from __future__ import annotations

import pytest

from commerce_lab.datagen.generator import generate_all, random_seed
from commerce_lab.datagen.plant_check import planted_scenario_failures


def test_random_seeds_differ():
    assert len({random_seed() for _ in range(20)}) > 1


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 6, 7, 8])
def test_every_seed_plants_all_four_scenarios_cleanly(seed):
    assert planted_scenario_failures(generate_all(seed=seed)) == []


def test_a_seed_reproduces_its_dataset_even_when_redrawn():
    # seed 2000 needs a redraw (see plant_check); it must still be reproducible
    a, b = generate_all(seed=2000), generate_all(seed=2000)
    assert a["orders"].equals(b["orders"]) and a["inventory"].equals(b["inventory"])
