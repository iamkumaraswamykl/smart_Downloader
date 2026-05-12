from smart_organizer.web import _bounded_int


def test_bounded_int_uses_default_for_invalid_values():
    assert _bounded_int("many", default=100, minimum=1, maximum=500) == 100
    assert _bounded_int("", default=100, minimum=1, maximum=500) == 100


def test_bounded_int_clamps_to_bounds():
    assert _bounded_int("-10", default=100, minimum=1, maximum=500) == 1
    assert _bounded_int("5000", default=100, minimum=1, maximum=500) == 500
