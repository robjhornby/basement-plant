from __future__ import annotations

from types import ModuleType

import basement_analysis


def test_package_imports() -> None:
    assert isinstance(basement_analysis, ModuleType)
