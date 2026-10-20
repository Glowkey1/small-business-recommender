from create_draft_relevance import (
    _capital_points,
    _label,
    _location_points,
    _setup_points,
    _time_points,
)


def test_capital_points_respect_start_small_and_full_setup():
    assert _capital_points(10000, 5000, 8000) == 2
    assert _capital_points(10000, 5000, 20000) == 1
    assert _capital_points(10000, 15000, 30000) == 0


def test_setup_points_require_a_compatible_setup():
    assert _setup_points("Online / Home-Based", ["Online"]) == (2, "compatible setup (Online / Home-Based)")
    assert _setup_points("Physical Store", ["Online"]) == (0, "incompatible setup (Physical Store)")


def test_time_points_scale_with_staffing_and_availability():
    assert _time_points("Solo", "1-2 hours/day")[0] == 2
    assert _time_points("2-6 staff", "1-2 hours/day")[0] == 1
    assert _time_points("5-20 workers", "1-2 hours/day")[0] == 0
    assert _time_points("5-20 workers", "5-6 hours/day")[0] == 2


def test_location_points_handle_missing_and_graded_scores():
    assert _location_points(None)[0] == 1
    assert _location_points(90)[0] == 2
    assert _location_points(75)[0] == 1
    assert _location_points(60)[0] == 0


def test_label_rejects_infeasible_capital_or_setup():
    assert _label(9, 0, 2) == 0
    assert _label(9, 2, 0) == 0
    assert _label(8, 2, 2) == 2
    assert _label(5, 2, 2) == 1
    assert _label(4, 2, 2) == 0
