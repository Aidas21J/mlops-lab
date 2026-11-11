import importlib.util
import json
import pathlib

import pytest

GATE_PATH = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "gate.py"


def load_gate():
    spec = importlib.util.spec_from_file_location("gate", GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "metrics").mkdir()
    (tmp_path / "params.yaml").write_text("gate:\n  metric: eval-f1\n  min: 0.75\n")
    monkeypatch.setenv("PARAMS_PATH", "params.yaml")
    monkeypatch.delenv("GATE_MIN", raising=False)
    return tmp_path


def write_scores(workdir, f1):
    (workdir / "metrics" / "scores.json").write_text(json.dumps({"eval-f1": f1}))


def test_gate_passes_above_threshold(workdir):
    write_scores(workdir, 0.80)
    assert load_gate().gate() is True


def test_gate_passes_at_threshold(workdir):
    write_scores(workdir, 0.75)
    assert load_gate().gate() is True


def test_gate_blocks_below_threshold(workdir):
    write_scores(workdir, 0.60)
    assert load_gate().gate() is False


def test_env_override_raises_the_bar(workdir, monkeypatch):
    write_scores(workdir, 0.80)
    monkeypatch.setenv("GATE_MIN", "0.90")
    assert load_gate().gate() is False


def test_cli_exit_code_is_1_when_blocked(workdir):
    write_scores(workdir, 0.60)
    with pytest.raises(SystemExit) as exc:
        load_gate().main(["gate.py", "gate"])
    assert exc.value.code == 1
