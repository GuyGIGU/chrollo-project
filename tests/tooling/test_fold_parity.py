"""Pure-logic pins for the Purity Pass parity instrument (tools/regression/fold_parity.py).

The instrument is the arbiter for every fold/rename commit of the pass, so its
three judgment calls are pinned: NaN equals NaN (and nothing else loosens),
the rename mapping renames keys at every depth, and an asymmetric key is a
reported difference, never a silent pass.
"""
from tools.regression.fold_parity import apply_mapping, diff_paths, exact_equal


def test_exact_equal_nan_and_exactness():
    assert exact_equal(float("nan"), float("nan"))
    assert exact_equal({"a": [1.0, float("nan")]}, {"a": [1.0, float("nan")]})
    # exactness: the 7th decimal that shadow's 6-dp rounding forgives is a diff here
    assert not exact_equal(0.1234567, 0.1234568)
    assert not exact_equal({"a": 1}, {"a": 1.0})  # int vs float: dict path
    assert not exact_equal(1, 1.0)  # type-strict on scalars


def test_apply_mapping_renames_at_depth():
    node = {"traversal_density": 1, "sub_scores": {"traversal_quality": 2}, "keep": [{"traversal_density": 3}]}
    out = apply_mapping(node, {"traversal_density": "equilibrium_density"})
    assert out["equilibrium_density"] == 1
    assert "traversal_density" not in out
    assert out["sub_scores"] == {"traversal_quality": 2}
    assert out["keep"][0] == {"equilibrium_density": 3}


def test_diff_paths_reports_asymmetric_keys():
    diffs = diff_paths({"a": 1, "gone": 2}, {"a": 1, "new": 3})
    joined = "\n".join(diffs)
    assert "gone" in joined and "ONLY IN CAPTURE" in joined
    assert "new" in joined and "ONLY IN CURRENT" in joined
    assert not diff_paths({"a": {"b": [1.0, 2.0]}}, {"a": {"b": [1.0, 2.0]}})
