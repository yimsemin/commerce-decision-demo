from __future__ import annotations

from commerce_lab.metrics.customer import new_vs_returning_mix, repeat_purchase_rate


def test_new_vs_returning_mix_shares_sum_to_one(datasets, window):
    mix = new_vs_returning_mix(datasets["orders"], window)
    assert abs(mix["current_new_share"] + mix["current_returning_share"] - 1) < 1e-6
    assert abs(mix["previous_new_share"] + mix["previous_returning_share"] - 1) < 1e-6


def test_repeat_purchase_rate_between_zero_and_one(datasets):
    rate = repeat_purchase_rate(datasets["customers"])
    assert 0.0 <= rate <= 1.0
