import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "process_batches.py"
SPEC = importlib.util.spec_from_file_location("process_batches", MODULE_PATH)
assert SPEC is not None
process_batches = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(process_batches)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_resume_skips_existing_patch_and_verified_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_json(Path("batches/detections_demo_batch_000.json"), [{"id": "001"}])
    _write_json(Path("out/patches_demo_batch_000.json"), [{"id": "001", "patch": []}])
    _write_json(Path("out/verified_demo_batch_000.json"), [{"id": "001", "accepted": True}])

    def fail_run(_cmd: list[str]) -> None:
        raise AssertionError("resume should skip existing proposer and verifier outputs")

    monkeypatch.setattr(process_batches, "_run", fail_run)

    process_batches.process_batches(
        detections_glob="batches/detections_demo_batch_*.json",
        config=Path("configs/run_grok.yaml"),
        patches_dir=Path("out"),
        verified_dir=Path("out"),
        jobs=2,
        proposer_extra=None,
        verifier_extra=None,
        resume=True,
        run_proposer=True,
        run_verifier=True,
    )


def test_batch_filter_and_extra_args_are_passed_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_json(Path("batches/detections_demo_batch_000.json"), [{"id": "000"}])
    _write_json(Path("batches/detections_demo_batch_001.json"), [{"id": "001"}])
    commands: list[list[str]] = []

    def fake_run(cmd: list[str]) -> None:
        commands.append(cmd)
        out_path = Path(cmd[cmd.index("--out") + 1])
        if "src.proposer.cli" in cmd:
            _write_json(out_path, [{"id": "001", "policy_id": "no_latest_tag", "patch": []}])
        else:
            _write_json(out_path, [{"id": "001", "accepted": True}])

    monkeypatch.setattr(process_batches, "_run", fake_run)

    process_batches.process_batches(
        detections_glob="batches/detections_demo_batch_*.json",
        config=Path("configs/run_grok.yaml"),
        patches_dir=Path("out"),
        verified_dir=Path("out"),
        jobs=3,
        proposer_extra=["--cache-dir", "tmp/cache"],
        verifier_extra=["--include-errors", "--jobs", "3"],
        resume=False,
        run_proposer=True,
        run_verifier=True,
        allowed_suffixes={"001"},
    )

    assert len(commands) == 2
    proposer_detections = commands[0][commands[0].index("--detections") + 1]
    assert proposer_detections == "batches/detections_demo_batch_001.json"
    assert proposer_detections != "batches/detections_demo_batch_000.json"
    assert commands[0][-2:] == ["--cache-dir", "tmp/cache"]
    assert commands[1][-3:] == ["--include-errors", "--jobs", "3"]


def test_unknown_batch_filter_fails_clearly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_json(Path("batches/detections_demo_batch_000.json"), [{"id": "000"}])

    with pytest.raises(FileNotFoundError, match="requested suffix"):
        process_batches.process_batches(
            detections_glob="batches/detections_demo_batch_*.json",
            config=Path("configs/run_grok.yaml"),
            patches_dir=Path("out"),
            verified_dir=Path("out"),
            jobs=1,
            proposer_extra=None,
            verifier_extra=None,
            resume=False,
            run_proposer=True,
            run_verifier=True,
            allowed_suffixes={"404"},
        )
