import io
import json
from pathlib import Path

import pytest

from scripts import run_tiny_regression


HOSTPATH_MANIFEST = """
apiVersion: v1
kind: Pod
metadata:
  name: hostpath-pod
spec:
  containers:
    - name: app
      image: nginx:1.25
      securityContext:
        capabilities:
          drop:
            - SYS_ADMIN
  volumes:
    - name: data
      hostPath:
        path: /var/lib/data
""".strip()


HOSTPORT_MANIFEST = """
apiVersion: v1
kind: Pod
metadata:
  name: hostport-pod
spec:
  containers:
    - name: app
      image: nginx:1.25
      securityContext:
        capabilities:
          drop:
            - SYS_ADMIN
      ports:
        - containerPort: 8080
          hostPort: 30080
""".strip()


def test_runner_reports_markdown_and_json_for_valid_pack(tmp_path: Path) -> None:
    pack = _write_valid_pack(tmp_path)

    code, stdout, stderr = _run(pack)

    assert code == 0
    assert stderr == ""
    assert "# Tiny Regression Report" in stdout
    assert "Status: **PASS**" in stdout
    assert "- Detector expectations: 2/2" in stdout
    assert "- Proposer/verifier cases: 2/2" in stdout
    assert "- Scheduler top: `hostpath`" in stdout
    assert "- Queue inserted: 2" in stdout
    assert "- Queue next: `hostpath`" in stdout

    json_code, json_stdout, json_stderr = _run(pack, "--json")
    payload = json.loads(json_stdout)

    assert json_code == 0
    assert json_stderr == ""
    assert payload["success"] is True
    assert payload["scheduler"]["top_id"] == "hostpath"
    assert payload["queue"]["inserted_count"] == 2
    assert payload["queue"]["next_id"] == "hostpath"


def test_validation_failure_reports_missing_manifest_path(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "cases.json",
        [
            {
                "id": "missing-manifest",
                "manifest_path": "manifests/missing.yaml",
                "policy_id": "no_host_ports",
                "expected_accepted": True,
                "risk": 1,
                "probability": 0.5,
                "expected_time": 1,
                "kev": False,
            }
        ],
    )
    _write_json(tmp_path / "detector_expectations.json", [])

    code, stdout, stderr = _run(tmp_path)

    assert code == 2
    assert stdout == ""
    assert "manifest_path not found" in stderr
    assert "manifests/missing.yaml" in stderr


def test_empty_pack_is_validation_failure(tmp_path: Path) -> None:
    _write_json(tmp_path / "cases.json", [])
    _write_json(tmp_path / "detector_expectations.json", [])

    code, stdout, stderr = _run(tmp_path)

    assert code == 2
    assert stdout == ""
    assert "cases.json must contain at least one case" in stderr


def test_regression_failure_reports_mismatched_expectation(tmp_path: Path) -> None:
    pack = _write_valid_pack(tmp_path)
    _write_json(
        pack / "detector_expectations.json",
        [
            {
                "id": "wrong-hostpath-rules",
                "manifest_path": "manifests/hostpath.yaml",
                "expected_rules": [],
            }
        ],
    )

    code, stdout, stderr = _run(pack)

    assert code == 1
    assert stderr == ""
    assert "Status: **FAIL**" in stdout
    assert "wrong-hostpath-rules" in stdout
    assert "expected rules [], got ['hostpath-volume']" in stdout


def test_scheduler_and_queue_expectations_are_enforced(tmp_path: Path) -> None:
    pack = _write_valid_pack(tmp_path)
    cases = json.loads((pack / "cases.json").read_text(encoding="utf-8"))
    cases[0]["expected_queue_next"] = False
    cases[1]["expected_scheduler_rank"] = 1
    cases[1]["expected_queue_next"] = True
    _write_json(pack / "cases.json", cases)

    code, stdout, stderr = _run(pack)

    assert code == 1
    assert stderr == ""
    assert "Status: **FAIL**" in stdout
    assert "scheduler `hostport`: expected rank 1, got 2" in stdout
    assert "queue `hostport`: expected next id 'hostport', got 'hostpath'" in stdout


def test_patch_override_can_drive_expected_rejection(tmp_path: Path) -> None:
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    (manifests / "hostport.yaml").write_text(HOSTPORT_MANIFEST, encoding="utf-8")
    _write_json(
        tmp_path / "cases.json",
        [
            {
                "id": "bad-override",
                "manifest_path": "manifests/hostport.yaml",
                "policy_id": "no_host_ports",
                "expected_accepted": False,
                "risk": 10,
                "probability": 0.9,
                "expected_time": 2,
                "kev": False,
                "patch_override": [
                    {"op": "add", "path": "/metadata/labels", "value": {"checked": "true"}}
                ],
            }
        ],
    )
    _write_json(
        tmp_path / "detector_expectations.json",
        [
            {
                "id": "hostport",
                "manifest_path": "manifests/hostport.yaml",
                "expected_rules": ["host-ports"],
            }
        ],
    )

    code, stdout, stderr = _run(tmp_path, "--json")
    payload = json.loads(stdout)

    assert code == 0
    assert stderr == ""
    assert payload["cases"]["results"][0]["accepted"] is False
    assert payload["cases"]["results"][0]["passed"] is True
    assert payload["scheduler"]["accepted_count"] == 0
    assert payload["queue"]["inserted_count"] == 0


def test_default_real_pack_runs_if_present() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    default_pack = repo_root / run_tiny_regression.DEFAULT_PACK_ROOT
    if not default_pack.exists():
        pytest.skip("default tiny regression pack is not present")

    code, stdout, stderr = _run(default_pack, "--json")

    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["success"] is True
    assert payload["detector"]["checked"] >= 6
    assert payload["cases"]["checked"] >= 6
    assert payload["scheduler"]["top_id"] == "tiny-no-privileged"
    assert payload["queue"]["next_id"] == "tiny-no-privileged"
    case_results = {case["id"]: case for case in payload["cases"]["results"]}
    assert case_results["tiny-env-var-secret"]["policy_id"] == "env_var_secret"
    assert case_results["tiny-env-var-secret"]["accepted"] is True
    assert case_results["tiny-env-var-secret"]["passed"] is True
    detector_results = {
        Path(result["manifest_path"]).name: result
        for result in payload["detector"]["results"]
    }
    assert detector_results["env-secret-pod.yaml"]["actual_rules"] == []
    assert detector_results["env-secret-pod.yaml"]["passed"] is True


def test_default_pack_path_is_repo_root_relative(monkeypatch, tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    default_pack = repo_root / run_tiny_regression.DEFAULT_PACK_ROOT.relative_to(repo_root)
    if not default_pack.exists():
        pytest.skip("default tiny regression pack is not present")
    monkeypatch.chdir(tmp_path)

    report = run_tiny_regression.run_pack(run_tiny_regression.DEFAULT_PACK_ROOT)

    assert report["success"] is True
    assert report["pack_root"] == str(default_pack.resolve())


def _write_valid_pack(root: Path) -> Path:
    manifests = root / "manifests"
    manifests.mkdir()
    (manifests / "hostpath.yaml").write_text(HOSTPATH_MANIFEST, encoding="utf-8")
    (manifests / "hostport.yaml").write_text(HOSTPORT_MANIFEST, encoding="utf-8")
    _write_json(
        root / "cases.json",
        [
            {
                "id": "hostpath",
                "manifest": "manifests/hostpath.yaml",
                "policy_id": "no_host_path",
                "expected_accepted": True,
                "risk": 90,
                "probability": 1.0,
                "expected_time": 2,
                "kev": True,
                "expected_scheduler_rank": 1,
                "expected_queue_next": True,
            },
            {
                "id": "hostport",
                "manifest_yaml": HOSTPORT_MANIFEST,
                "policy_id": "host-ports",
                "expected_accepted": True,
                "risk": 25,
                "probability": 0.8,
                "expected_time": 5,
                "kev": False,
            },
        ],
    )
    _write_json(
        root / "detector_expectations.json",
        [
            {
                "id": "hostpath",
                "manifest_path": "manifests/hostpath.yaml",
                "expected_rules": ["hostpath-volume"],
            },
            {
                "id": "hostport",
                "manifest_path": "manifests/hostport.yaml",
                "expected_rules": ["host-ports"],
            },
        ],
    )
    return root


def _run(pack: Path, *args: str) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = run_tiny_regression.main([str(pack), *args], stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
