import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = PROJECT_ROOT / "Makefile"
README = PROJECT_ROOT / "README.md"
SCRIPTS_README = PROJECT_ROOT / "scripts" / "README.md"

KEY_SMOKE_TARGETS = {
    "artifact-index-smoke",
    "artifact-traceability-smoke",
    "docs-link-check",
    "evidence-manifest-claims-smoke",
    "evidence-manifest-pipeline-smoke",
    "evidence-manifest-smoke",
    "gitops-plan-smoke",
    "metrics-consistency",
    "patch-diff-smoke",
    "pipeline-manifest-smoke",
    "pipeline-plan",
    "pipeline-status-smoke",
    "queue-report-smoke",
    "review-packet-concise-smoke",
    "review-packet-rollout-smoke",
    "review-packet-smoke",
    "scheduler-batches-smoke",
    "scheduler-explain-smoke",
    "tiny-regression",
}


def _make_targets() -> set[str]:
    text = MAKEFILE.read_text(encoding="utf-8")
    return set(re.findall(r"^([A-Za-z0-9][A-Za-z0-9_.-]*):(?!=)", text, flags=re.MULTILINE))


def _documented_make_targets(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return {
        match.group(1)
        for match in re.finditer(r"(?:`make|(?<![\w-])make)\s+([A-Za-z0-9_.-]+)", text)
    }


def _documented_scripts_from_root_readme() -> set[Path]:
    text = README.read_text(encoding="utf-8")
    return {
        PROJECT_ROOT / match.group(1)
        for match in re.finditer(r"`?(scripts/[A-Za-z0-9_./-]+\.(?:py|sh|md))`?", text)
    }


def _documented_scripts_from_scripts_readme() -> set[Path]:
    text = SCRIPTS_README.read_text(encoding="utf-8")
    return {
        PROJECT_ROOT / "scripts" / match.group(1)
        for match in re.finditer(r"`([A-Za-z0-9_.-]+\.(?:py|sh))`", text)
    }


def test_readme_make_targets_exist() -> None:
    targets = _make_targets()
    documented = _documented_make_targets(README) | _documented_make_targets(SCRIPTS_README)

    missing = sorted(documented - targets)

    assert not missing, f"README documents missing Make targets: {missing}"


def test_readme_script_references_exist() -> None:
    documented_scripts = _documented_scripts_from_root_readme() | _documented_scripts_from_scripts_readme()

    missing = sorted(str(path.relative_to(PROJECT_ROOT)) for path in documented_scripts if not path.exists())

    assert not missing, f"README documents missing helper scripts: {missing}"


def test_key_smoke_targets_remain_documented_and_implemented() -> None:
    targets = _make_targets()
    readme_targets = _documented_make_targets(README)

    missing_from_makefile = sorted(KEY_SMOKE_TARGETS - targets)
    missing_from_readme = sorted(KEY_SMOKE_TARGETS - readme_targets)

    assert not missing_from_makefile, f"Key smoke Make targets disappeared: {missing_from_makefile}"
    assert not missing_from_readme, f"Key smoke Make targets are no longer documented: {missing_from_readme}"
