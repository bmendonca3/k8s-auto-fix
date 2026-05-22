import io
import json
import subprocess
from pathlib import Path

from scripts import gitops_writeback


POD_MANIFEST = """\
apiVersion: v1
kind: Pod
metadata:
  name: demo
spec:
  containers:
  - name: web
    image: nginx:latest
"""


def test_plan_out_reports_skip_reasons_without_touching_git_or_manifests(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manifest = tmp_path / "manifests" / "pod.yaml"
    manifest.parent.mkdir()
    manifest.write_text(POD_MANIFEST, encoding="utf-8")
    original_manifest = manifest.read_text(encoding="utf-8")
    detections_path = tmp_path / "detections.json"
    verified_path = tmp_path / "verified.json"
    plan_path = tmp_path / "plan.json"
    detections_path.write_text(
        json.dumps(
            [
                {"id": "accepted", "manifest_path": "manifests/pod.yaml"},
                {"id": "missing-manifest"},
                {"id": "outside", "manifest_path": "../outside.yaml"},
                {"id": "missing-file", "manifest_path": "manifests/missing.yaml"},
                {"id": "invalid", "manifest_path": "manifests/pod.yaml"},
                {"id": "rejected", "manifest_path": "manifests/pod.yaml"},
            ]
        ),
        encoding="utf-8",
    )
    verified_path.write_text(
        json.dumps(
            [
                {
                    "id": "accepted",
                    "accepted": True,
                    "patch": [
                        {
                            "op": "replace",
                            "path": "/spec/containers/0/image",
                            "value": "nginx:stable",
                        }
                    ],
                },
                {
                    "id": "missing-manifest",
                    "accepted": True,
                    "patch": [{"op": "replace", "path": "/kind", "value": "ConfigMap"}],
                },
                {
                    "id": "outside",
                    "accepted": True,
                    "patch": [{"op": "replace", "path": "/kind", "value": "ConfigMap"}],
                },
                {
                    "id": "missing-file",
                    "accepted": True,
                    "patch": [{"op": "replace", "path": "/kind", "value": "ConfigMap"}],
                },
                {
                    "id": "invalid",
                    "accepted": True,
                    "patch": [
                        {
                            "op": "replace",
                            "path": "/spec/containers/9/image",
                            "value": "nginx:stable",
                        }
                    ],
                },
                {
                    "id": "rejected",
                    "accepted": False,
                    "patch": [{"op": "replace", "path": "/kind", "value": "ConfigMap"}],
                },
            ]
        ),
        encoding="utf-8",
    )

    def fail_run(*_args, **_kwargs):
        raise AssertionError("dry-run planning must not call git")

    monkeypatch.setattr(gitops_writeback, "run", fail_run)
    stdout = io.StringIO()

    code = gitops_writeback.main(
        [
            "--detections",
            str(detections_path),
            "--verified",
            str(verified_path),
            "--repo-root",
            str(tmp_path),
            "--plan-out",
            str(plan_path),
        ],
        stdout=stdout,
    )

    assert code == 0
    assert manifest.read_text(encoding="utf-8") == original_manifest
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["summary"] == {
        "would_modify": 1,
        "skipped": 5,
        "files_would_modify": 1,
    }
    assert plan["files_would_modify"] == ["manifests/pod.yaml"]
    assert {entry["reason"] for entry in plan["skipped"]} == {
        "missing_manifest_path",
        "unsafe_outside_repo_path",
        "missing_file",
        "invalid_patch_application",
        "rejected_patch",
    }
    output = stdout.getvalue()
    assert "GitOps writeback plan (dry run)" in output
    assert "unsafe_outside_repo_path" in output
    assert "invalid_patch_application" in output


def test_plan_out_creates_parent_directories(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "pod.yaml"
    manifest.write_text(POD_MANIFEST, encoding="utf-8")
    detections_path = tmp_path / "detections.json"
    verified_path = tmp_path / "verified.json"
    plan_path = tmp_path / "nested" / "plans" / "writeback.json"
    detections_path.write_text(
        json.dumps([{"id": "accepted", "manifest_path": "pod.yaml"}]),
        encoding="utf-8",
    )
    verified_path.write_text(
        json.dumps(
            [
                {
                    "id": "accepted",
                    "accepted": True,
                    "patch": [{"op": "replace", "path": "/kind", "value": "ConfigMap"}],
                }
            ]
        ),
        encoding="utf-8",
    )

    def fail_run(*_args, **_kwargs):
        raise AssertionError("plan-out must not call git")

    monkeypatch.setattr(gitops_writeback, "run", fail_run)

    code = gitops_writeback.main(
        [
            "--detections",
            str(detections_path),
            "--verified",
            str(verified_path),
            "--repo-root",
            str(tmp_path),
            "--plan-out",
            str(plan_path),
        ],
        stdout=io.StringIO(),
    )

    assert code == 0
    assert plan_path.exists()


def test_write_mode_applies_valid_patches_with_git_commands_monkeypatched(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manifest = tmp_path / "manifests" / "pod.yaml"
    manifest.parent.mkdir()
    manifest.write_text(POD_MANIFEST, encoding="utf-8")
    detections_path = tmp_path / "detections.json"
    verified_path = tmp_path / "verified.json"
    detections_path.write_text(
        json.dumps(
            [
                {"id": "accepted", "manifest_path": "manifests/pod.yaml"},
                {"id": "rejected", "manifest_path": "manifests/pod.yaml"},
            ]
        ),
        encoding="utf-8",
    )
    verified_path.write_text(
        json.dumps(
            [
                {
                    "id": "accepted",
                    "ok_policy": True,
                    "ok_schema": True,
                    "ok_safety": True,
                    "patch_ops": [
                        {
                            "op": "replace",
                            "path": "/spec/containers/0/image",
                            "value": "nginx:stable",
                        }
                    ],
                },
                {
                    "id": "rejected",
                    "accepted": False,
                    "patch": [{"op": "replace", "path": "/kind", "value": "ConfigMap"}],
                },
            ]
        ),
        encoding="utf-8",
    )
    run_calls = []

    def fake_run(cmd, cwd=None, check=True):
        run_calls.append((cmd, cwd, check))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(gitops_writeback, "run", fake_run)
    stdout = io.StringIO()

    code = gitops_writeback.main(
        [
            "--detections",
            str(detections_path),
            "--verified",
            str(verified_path),
            "--repo-root",
            str(tmp_path),
            "--branch",
            "test-branch",
            "--no-pr",
        ],
        stdout=stdout,
    )

    assert code == 0
    assert "image: nginx:stable" in manifest.read_text(encoding="utf-8")
    assert [call[0] for call in run_calls] == [
        ["git", "rev-parse", "--is-inside-work-tree"],
        ["git", "diff", "--quiet", "--", "manifests/pod.yaml"],
        ["git", "diff", "--cached", "--quiet", "--", "manifests/pod.yaml"],
        ["git", "checkout", "-B", "test-branch"],
        ["git", "add", str(manifest.resolve())],
        ["git", "commit", "-m", "k8s-auto-fix: apply verified patches"],
    ]
    output = stdout.getvalue()
    assert "[skip] manifests/pod.yaml (id=rejected): rejected_patch" in output
    assert "Modified 1 file(s). Branch test-branch is ready." in output


def test_write_mode_does_not_create_pr_by_default(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "manifests" / "pod.yaml"
    manifest.parent.mkdir()
    manifest.write_text(POD_MANIFEST, encoding="utf-8")
    detections_path = tmp_path / "detections.json"
    verified_path = tmp_path / "verified.json"
    detections_path.write_text(
        json.dumps([{"id": "accepted", "manifest_path": "manifests/pod.yaml"}]),
        encoding="utf-8",
    )
    verified_path.write_text(
        json.dumps(
            [
                {
                    "id": "accepted",
                    "accepted": True,
                    "patch": [{"op": "replace", "path": "/spec/containers/0/image", "value": "nginx:stable"}],
                }
            ]
        ),
        encoding="utf-8",
    )

    def fake_run(cmd, cwd=None, check=True):
        return subprocess.CompletedProcess(cmd, 0)

    def fail_create_pr(*_args, **_kwargs):
        raise AssertionError("PR creation must be opt-in")

    monkeypatch.setattr(gitops_writeback, "run", fake_run)
    monkeypatch.setattr(gitops_writeback, "create_pull_request", fail_create_pr)

    code = gitops_writeback.main(
        [
            "--detections",
            str(detections_path),
            "--verified",
            str(verified_path),
            "--repo-root",
            str(tmp_path),
        ],
        stdout=io.StringIO(),
    )

    assert code == 0


def test_create_pr_verifies_remote_host_before_gh(tmp_path: Path, monkeypatch) -> None:
    calls = []

    def fake_subprocess_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        if cmd == ["git", "remote", "get-url", "origin"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="git@github.gatech.edu:org/repo.git\n")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(cmd, 0)
        raise AssertionError(f"unexpected subprocess call: {cmd}")

    monkeypatch.setattr(gitops_writeback.subprocess, "run", fake_subprocess_run)

    gitops_writeback.create_pull_request(tmp_path, io.StringIO())

    assert calls[0][0] == ["git", "remote", "get-url", "origin"]
    assert calls[1][0] == ["gh", "pr", "create", "--fill"]
    assert calls[1][1]["env"]["GH_HOST"] == "github.gatech.edu"


def test_github_host_from_remote_rejects_lookalike_hosts(tmp_path: Path, monkeypatch) -> None:
    remotes = iter(
        [
            "https://github.com.evil.example/org/repo.git\n",
            "ssh://git@evil.example/github.com/org/repo.git\n",
        ]
    )

    def fake_subprocess_run(cmd, **kwargs):
        assert cmd == ["git", "remote", "get-url", "origin"]
        return subprocess.CompletedProcess(cmd, 0, stdout=next(remotes))

    monkeypatch.setattr(gitops_writeback.subprocess, "run", fake_subprocess_run)

    for _ in range(2):
        try:
            gitops_writeback.github_host_from_remote(tmp_path)
        except RuntimeError as exc:
            assert "Unsupported GitHub remote host" in str(exc)
        else:  # pragma: no cover - assertion path
            raise AssertionError("lookalike remote host should be rejected")


def test_github_host_from_remote_accepts_exact_hosts(tmp_path: Path, monkeypatch) -> None:
    remotes = iter(
        [
            ("https://github.com/org/repo.git\n", "github.com"),
            ("git@github.gatech.edu:org/repo.git\n", "github.gatech.edu"),
        ]
    )

    def fake_subprocess_run(cmd, **kwargs):
        assert cmd == ["git", "remote", "get-url", "origin"]
        remote, _expected = next(remotes)
        return subprocess.CompletedProcess(cmd, 0, stdout=remote)

    monkeypatch.setattr(gitops_writeback.subprocess, "run", fake_subprocess_run)

    assert gitops_writeback.github_host_from_remote(tmp_path) == "github.com"
    assert gitops_writeback.github_host_from_remote(tmp_path) == "github.gatech.edu"


def test_write_mode_does_not_checkout_when_every_patch_is_skipped(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manifest = tmp_path / "manifests" / "pod.yaml"
    manifest.parent.mkdir()
    manifest.write_text(POD_MANIFEST, encoding="utf-8")
    detections_path = tmp_path / "detections.json"
    verified_path = tmp_path / "verified.json"
    detections_path.write_text(
        json.dumps([{"id": "rejected", "manifest_path": "manifests/pod.yaml"}]),
        encoding="utf-8",
    )
    verified_path.write_text(
        json.dumps(
            [
                {
                    "id": "rejected",
                    "accepted": False,
                    "patch": [{"op": "replace", "path": "/kind", "value": "ConfigMap"}],
                }
            ]
        ),
        encoding="utf-8",
    )
    run_calls = []

    def fake_run(cmd, cwd=None, check=True):
        run_calls.append((cmd, cwd, check))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(gitops_writeback, "run", fake_run)
    stdout = io.StringIO()

    code = gitops_writeback.main(
        [
            "--detections",
            str(detections_path),
            "--verified",
            str(verified_path),
            "--repo-root",
            str(tmp_path),
            "--branch",
            "test-branch",
            "--no-pr",
        ],
        stdout=stdout,
    )

    assert code == 0
    assert [call[0] for call in run_calls] == [["git", "rev-parse", "--is-inside-work-tree"]]
    assert "No files modified; exiting" in stdout.getvalue()


def test_write_mode_preserves_multi_document_yaml(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "manifests" / "multi.yaml"
    manifest.parent.mkdir()
    manifest.write_text(
        POD_MANIFEST
        + "---\napiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: settings\ndata:\n  mode: unsafe\n",
        encoding="utf-8",
    )
    detections_path = tmp_path / "detections.json"
    verified_path = tmp_path / "verified.json"
    detections_path.write_text(
        json.dumps(
            [
                {
                    "id": "accepted",
                    "manifest_path": "manifests/multi.yaml",
                    "document_index": 1,
                }
            ]
        ),
        encoding="utf-8",
    )
    verified_path.write_text(
        json.dumps(
            [
                {
                    "id": "accepted",
                    "accepted": True,
                    "patch": [{"op": "replace", "path": "/data/mode", "value": "safe"}],
                }
            ]
        ),
        encoding="utf-8",
    )

    def fake_run(cmd, cwd=None, check=True):
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(gitops_writeback, "run", fake_run)

    code = gitops_writeback.main(
        [
            "--detections",
            str(detections_path),
            "--verified",
            str(verified_path),
            "--repo-root",
            str(tmp_path),
            "--no-pr",
        ],
        stdout=io.StringIO(),
    )

    assert code == 0
    docs = list(gitops_writeback.yaml.safe_load_all(manifest.read_text(encoding="utf-8")))
    assert len(docs) == 2
    assert docs[0]["kind"] == "Pod"
    assert docs[1]["data"]["mode"] == "safe"


def test_require_kubectl_verifies_modified_files_before_commit(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "manifests" / "pod.yaml"
    manifest.parent.mkdir()
    manifest.write_text(POD_MANIFEST, encoding="utf-8")
    detections_path = tmp_path / "detections.json"
    verified_path = tmp_path / "verified.json"
    detections_path.write_text(
        json.dumps([{"id": "accepted", "manifest_path": "manifests/pod.yaml"}]),
        encoding="utf-8",
    )
    verified_path.write_text(
        json.dumps(
            [
                {
                    "id": "accepted",
                    "accepted": True,
                    "patch": [{"op": "replace", "path": "/spec/containers/0/image", "value": "nginx:stable"}],
                }
            ]
        ),
        encoding="utf-8",
    )
    run_calls = []

    def fake_run(cmd, cwd=None, check=True):
        run_calls.append((cmd, cwd, check))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(gitops_writeback, "run", fake_run)

    code = gitops_writeback.main(
        [
            "--detections",
            str(detections_path),
            "--verified",
            str(verified_path),
            "--repo-root",
            str(tmp_path),
            "--branch",
            "test-branch",
            "--require-kubectl",
            "--no-pr",
        ],
        stdout=io.StringIO(),
    )

    assert code == 0
    commands = [call[0] for call in run_calls]
    kubectl_index = commands.index(["kubectl", "apply", "--dry-run=server", "-f", str(manifest.resolve())])
    commit_index = commands.index(["git", "commit", "-m", "k8s-auto-fix: apply verified patches"])
    assert kubectl_index < commit_index


def test_require_kubectl_failure_stops_before_commit(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "manifests" / "pod.yaml"
    manifest.parent.mkdir()
    manifest.write_text(POD_MANIFEST, encoding="utf-8")
    detections_path = tmp_path / "detections.json"
    verified_path = tmp_path / "verified.json"
    detections_path.write_text(
        json.dumps([{"id": "accepted", "manifest_path": "manifests/pod.yaml"}]),
        encoding="utf-8",
    )
    verified_path.write_text(
        json.dumps(
            [
                {
                    "id": "accepted",
                    "accepted": True,
                    "patch": [{"op": "replace", "path": "/spec/containers/0/image", "value": "nginx:stable"}],
                }
            ]
        ),
        encoding="utf-8",
    )
    run_calls = []

    def fake_run(cmd, cwd=None, check=True):
        run_calls.append((cmd, cwd, check))
        if cmd[:3] == ["kubectl", "apply", "--dry-run=server"]:
            raise subprocess.CalledProcessError(1, cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(gitops_writeback, "run", fake_run)

    try:
        gitops_writeback.main(
            [
                "--detections",
                str(detections_path),
                "--verified",
                str(verified_path),
                "--repo-root",
                str(tmp_path),
                "--require-kubectl",
                "--no-pr",
            ],
            stdout=io.StringIO(),
        )
    except subprocess.CalledProcessError:
        pass
    else:  # pragma: no cover - assertion path
        raise AssertionError("kubectl failure should stop writeback")

    commands = [call[0] for call in run_calls]
    assert ["git", "commit", "-m", "k8s-auto-fix: apply verified patches"] not in commands
