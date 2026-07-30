from scripts.check_runtime_dependencies import version_tuple


def test_runtime_dependency_versions_are_compared_numerically() -> None:
    assert version_tuple("1.2.10") > version_tuple("1.2.9")
    assert version_tuple("83.0.0") >= (78, 1, 1)
