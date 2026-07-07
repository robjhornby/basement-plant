from __future__ import annotations

import sys

import pytest

from basement_analysis import cli


def test_main_dispatches_subcommands_from_console_script_argv(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["basement", "curate-ingested-r2", "--help"])

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 0
    assert "Merge accepted X-Sense CSV objects" in capsys.readouterr().out
