from __future__ import annotations

from commerce_lab.datagen.generator import generate_all


def test_same_seed_produces_identical_output():
    a = generate_all(seed=42)
    b = generate_all(seed=42)

    for name in a:
        assert a[name].equals(b[name]), f"dataset '{name}' is not deterministic for a fixed seed"


def test_different_seed_produces_different_orders():
    a = generate_all(seed=42)
    b = generate_all(seed=7)

    assert not a["orders"].equals(b["orders"])
