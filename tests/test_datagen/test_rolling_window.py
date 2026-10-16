import datetime as dt

from commerce_lab.datagen import config


def test_end_date_can_be_pinned(monkeypatch):
    monkeypatch.setenv("COMMERCE_END_DATE", "2027-01-15")
    assert config._resolve_end_date() == dt.date(2027, 1, 15)


def test_end_date_defaults_to_today_in_korea(monkeypatch):
    monkeypatch.delenv("COMMERCE_END_DATE", raising=False)
    kst_today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    assert abs((config._resolve_end_date() - kst_today).days) <= 1  # tolerate a midnight rollover mid-test


def test_windows_are_derived_from_end_date():
    assert config.START_DATE == config.END_DATE - dt.timedelta(days=config.TOTAL_DAYS - 1)
    assert config.RECENT_START_DATE == config.END_DATE - dt.timedelta(days=config.RECENT_WINDOW_DAYS - 1)
