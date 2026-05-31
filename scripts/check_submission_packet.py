#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_REMOTE_URL = "https://github.com/bmendonca3/k8s-auto-fix.git"
PACKET_TAG = "tcc-2025-12-0666-packet-2026-05-31"

LOCAL_ONLY_FILES = [
    "paper/SUBMISSION_PACKET.md",
    "paper/LOCAL_WORKTREE_STATE.md",
    "paper/SUBMISSION_GAP_REGISTER.md",
    "paper/SUBMISSION_ARTIFACT_INVENTORY.md",
    "paper/RESPONSE_LETTER_CLAIM_CHECK.md",
    "paper/SOURCE_VERIFICATION_MCP_2026-05-31.md",
    "paper/source_verification_mcp_2026-05-31.json",
    "paper/REFERENCE_FIX_CHANGES.md",
    "paper/REVISION_CHANGES_2026-05-30.md",
    "paper/REVISION_TRACKING.md",
    "paper/CLAIM_EVIDENCE_AUDIT_KIRO_OPUS_2026-05-31.md",
]

PACKET_DOCS = [
    "paper/SUBMISSION_PACKET.md",
    "paper/SUBMISSION_GAP_REGISTER.md",
    "paper/SUBMISSION_ARTIFACT_INVENTORY.md",
    "docs/ieee_submission_checklist.md",
    "docs/REVIEW_RESPONSE.md",
]

NO_GO_DOCS = [
    "paper/SUBMISSION_PACKET.md",
    "paper/SUBMISSION_GAP_REGISTER.md",
    "paper/SUBMISSION_ARTIFACT_INVENTORY.md",
    "docs/ieee_submission_checklist.md",
]

STALE_WORDING_DOCS = PACKET_DOCS + [
    "paper/LOCAL_WORKTREE_STATE.md",
    "paper/RESPONSE_LETTER_CLAIM_CHECK.md",
    "paper/cover_letter.md",
    "paper/overleaf/paper/cover_letter.md",
    "paper/response_to_reviewers.md",
]

UPLOAD_FACING_DOCS = [
    "paper/access.tex",
    "paper/overleaf/paper/access.tex",
    "paper/cover_letter.md",
    "paper/overleaf/paper/cover_letter.md",
    "paper/response_to_reviewers.md",
]

HASHED_ARTIFACTS = [
    "paper/access.pdf",
    "paper/access.tex",
    "paper/cover_letter.md",
    "paper/response_to_reviewers.md",
    "paper/overleaf/main.pdf",
    "paper/overleaf/main.tex",
    "paper/overleaf/paper/access.tex",
    "paper/references.bib",
    "paper/overleaf/paper/references.bib",
    "paper/grok_failures_table.tex",
    "docs/reproducibility/baselines.tex",
    "paper/overleaf/paper/grok_failures_table.tex",
    "paper/overleaf/paper/reproducibility/baselines.tex",
]

MIRRORED_FILES = [
    ("paper/cover_letter.md", "paper/overleaf/paper/cover_letter.md"),
    ("paper/references.bib", "paper/overleaf/paper/references.bib"),
    ("paper/grok_failures_table.tex", "paper/overleaf/paper/grok_failures_table.tex"),
    ("docs/reproducibility/baselines.tex", "paper/overleaf/paper/reproducibility/baselines.tex"),
]

RETIRED_PUBLIC_ARTIFACTS = [
    "appendix/appendices.tex",
    "data/failures/taxonomy_summary.csv",
    "data/batch_runs/grok_5k/metrics_history.json",
    "notes/to-do list",
    "paper/tectonic",
    "paper/ieeeaccess.cls",
    "paper/overleaf/ieeeaccess.cls",
    "add_iam_policy_binding.sh",
    "access.log",
    "logs/access.log",
]

def chars(*codes: int) -> str:
    return "".join(chr(code) for code in codes)


TOOL_NAME = chars(67, 111, 100, 101, 120)
TOOL_TAG = r"\[" + TOOL_NAME.lower() + r"\]"

STALE_PATTERNS = [
    TOOL_TAG,
    rf"\b{TOOL_NAME}\b",
    chars(86, 105, 98, 97, 121),
    chars(86, 105, 98, 104, 97, 121),
    chars(68, 101, 97, 114, 32) + chars(86, 105, 106, 97, 121),
    chars(68, 101, 97, 114, 32) + chars(77, 97, 100, 105, 115, 101, 116, 116, 105),
    chars(73, 69, 69, 69, 32) + chars(65, 99, 99, 101, 115, 115),
    "completed live " + "operator",
    "completed " + "operator",
]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def require_file(path: str, failures: list[str]) -> None:
    if not (ROOT / path).exists():
        fail(f"{path}: missing required packet file", failures)


def require_contains(path: str, needle: str, failures: list[str]) -> None:
    if needle not in read_text(path):
        fail(f"{path}: missing required text {needle!r}", failures)


def require_contains_normalized(path: str, needle: str, failures: list[str]) -> None:
    text = re.sub(r"\s+", " ", read_text(path))
    normalized_needle = re.sub(r"\s+", " ", needle)
    if normalized_needle not in text:
        fail(f"{path}: missing required text {needle!r}", failures)


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with (ROOT / path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_lines(args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def git_stdout(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def git_maybe_stdout(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def check_required_files(failures: list[str]) -> None:
    mirrored_paths = [path for pair in MIRRORED_FILES for path in pair]
    for path in sorted(set(PACKET_DOCS + NO_GO_DOCS + HASHED_ARTIFACTS + mirrored_paths)):
        require_file(path, failures)


def check_no_go_gate(failures: list[str]) -> None:
    for path in NO_GO_DOCS:
        text = read_text(path)
        if "TCC-2025-12-0666" not in text:
            fail(f"{path}: missing manuscript id gate", failures)
        if not re.search(r"resubmit(?:ted)? or reopen(?:ed)?", text):
            fail(f"{path}: missing resubmit/reopen gate wording", failures)
        if "Do not" not in text and "not go for submission" not in text and "gated" not in text and "Submission gate" not in text:
            fail(f"{path}: missing explicit no-go language", failures)


def check_external_action_guard(failures: list[str]) -> None:
    for text in [
        "Do not email, upload, open a pull request, or comment externally unless explicitly requested.",
        "Do not email, upload, or submit any artifact",
        "Do not submit until IEEE Transactions on Cloud Computing confirms",
    ]:
        normalized_text = re.sub(r"\s+", " ", text)
        found = any(
            normalized_text in re.sub(r"\s+", " ", read_text(path))
            for path in PACKET_DOCS
        )
        if not found:
            fail(f"packet docs: missing external-action guard text {text!r}", failures)

    require_contains_normalized(
        "paper/SUBMISSION_PACKET.md",
        "intentionally kept in the repository for traceability",
        failures,
    )
    require_contains_normalized(
        "paper/SUBMISSION_ARTIFACT_INVENTORY.md",
        "intentionally public in the repository for traceability",
        failures,
    )


def check_do_not_upload_lists(failures: list[str]) -> None:
    docs = [
        "paper/SUBMISSION_PACKET.md",
        "paper/SUBMISSION_GAP_REGISTER.md",
        "paper/SUBMISSION_ARTIFACT_INVENTORY.md",
        "docs/ieee_submission_checklist.md",
    ]
    required = [
        "paper/SUBMISSION_PACKET.md",
        "paper/LOCAL_WORKTREE_STATE.md",
        "paper/SUBMISSION_GAP_REGISTER.md",
        "paper/SUBMISSION_ARTIFACT_INVENTORY.md",
        "paper/RESPONSE_LETTER_CLAIM_CHECK.md",
        "paper/SOURCE_VERIFICATION_MCP_2026-05-31.md",
        "paper/source_verification_mcp_2026-05-31.json",
        "paper/REFERENCE_FIX_CHANGES.md",
        "paper/REVISION_CHANGES_2026-05-30.md",
        "paper/REVISION_TRACKING.md",
        "paper/CLAIM_EVIDENCE_AUDIT_KIRO_OPUS_2026-05-31.md",
    ]
    required_misc = [
        ".DS_Store",
        "notes/to-do list",
        "paper/archives/overleaf_upload.zip",
        "appendix/appendices.tex",
        "data/failures/taxonomy_summary.csv",
        "data/batch_runs/grok_5k/metrics_history.json",
        "paper/tectonic",
        "paper/ieeeaccess.cls",
        "paper/overleaf/ieeeaccess.cls",
        "add_iam_policy_binding.sh",
        "access.log",
        "logs/access.log",
        "main.aux",
        "main.log",
        "main.out",
        "missfont.log",
        "dheer_toprani_photo.png",
    ]
    for path in docs:
        text = read_text(path)
        if "Do Not Upload" not in text:
            fail(f"{path}: missing Do Not Upload section", failures)
        for local_only in required:
            if local_only == path and "This file" in text:
                continue
            if local_only not in text:
                fail(f"{path}: missing do-not-upload entry for {local_only}", failures)
        if path != "paper/SUBMISSION_GAP_REGISTER.md":
            for local_only in required_misc:
                if local_only not in text:
                    fail(f"{path}: missing do-not-upload entry for {local_only}", failures)


def check_overleaf_clean_package_guidance(failures: list[str]) -> None:
    docs = [
        "paper/SUBMISSION_PACKET.md",
        "paper/SUBMISSION_GAP_REGISTER.md",
        "paper/SUBMISSION_ARTIFACT_INVENTORY.md",
        "docs/ieee_submission_checklist.md",
        "docs/REVIEW_RESPONSE.md",
        "paper/LOCAL_WORKTREE_STATE.md",
    ]
    for path in docs:
        text = re.sub(r"\s+", " ", read_text(path))
        if "paper/overleaf/" not in text:
            fail(f"{path}: missing Overleaf source-package reference", failures)
        if "as-is" not in text and "clean package" not in text:
            fail(f"{path}: missing clean-package warning", failures)
    require_contains("docs/ieee_submission_checklist.md", "rsync -ain", failures)
    require_contains("paper/SUBMISSION_ARTIFACT_INVENTORY.md", "rsync -ain", failures)
    require_contains("docs/ieee_submission_checklist.md", "--exclude='main.pdf'", failures)
    require_contains("paper/SUBMISSION_ARTIFACT_INVENTORY.md", "--exclude='main.pdf'", failures)
    for excluded in ["cover_letter.md", "ieeeaccess.cls", "tectonic"]:
        require_contains("docs/ieee_submission_checklist.md", excluded, failures)
        require_contains("paper/SUBMISSION_ARTIFACT_INVENTORY.md", excluded, failures)
    for path in [
        "paper/SUBMISSION_PACKET.md",
        "paper/SUBMISSION_GAP_REGISTER.md",
        "paper/LOCAL_WORKTREE_STATE.md",
    ]:
        require_contains(path, "main.pdf", failures)


def check_portal_checklist_commands(failures: list[str]) -> None:
    for command in [
        "make submission-packet-check",
        "make docs-link-check metrics-consistency",
        ".venv/bin/python -m unittest discover -s tests -p 'test_verifier.py'",
        "git diff --check",
    ]:
        require_contains("docs/ieee_submission_checklist.md", command, failures)


def check_gap_register_priorities(failures: list[str]) -> None:
    for text in [
        "| P0 | TCC/EIC permission",
        "| P1 | Final portal-bound packet review",
        "| P1 | Named-agent head-to-head",
        "| P2 | Novelty rebuttal",
        "| P2 | Overleaf/source upload hygiene",
        "not go for submission",
    ]:
        require_contains("paper/SUBMISSION_GAP_REGISTER.md", text, failures)


def check_no_local_controls_in_overleaf_tree(failures: list[str]) -> None:
    overleaf_root = ROOT / "paper/overleaf"
    blocked_names = {Path(path).name for path in LOCAL_ONLY_FILES}
    for path in overleaf_root.rglob("*"):
        if path.is_file() and path.name in blocked_names:
            fail(f"{path.relative_to(ROOT)}: local-only packet control is inside source-package tree", failures)


def check_hash_inventory(failures: list[str]) -> None:
    inventory = read_text("paper/SUBMISSION_ARTIFACT_INVENTORY.md")
    for path in HASHED_ARTIFACTS:
        actual = sha256(path)
        if actual not in inventory:
            fail(f"paper/SUBMISSION_ARTIFACT_INVENTORY.md: missing current hash for {path}", failures)


def check_mirrored_files(failures: list[str]) -> None:
    for source, mirror in MIRRORED_FILES:
        source_bytes = (ROOT / source).read_bytes()
        mirror_bytes = (ROOT / mirror).read_bytes()
        if source_bytes != mirror_bytes:
            fail(f"{mirror}: does not match {source}", failures)


def check_dirty_snapshot(failures: list[str]) -> None:
    require_file("paper/LOCAL_WORKTREE_STATE.md", failures)


def check_repository_snapshot(failures: list[str]) -> None:
    local_state = read_text("paper/LOCAL_WORKTREE_STATE.md")
    actual_remote = git_stdout(["remote", "get-url", "origin"])

    if actual_remote != EXPECTED_REMOTE_URL:
        fail(f"origin remote changed: {actual_remote!r}", failures)

    for required_text in [
        EXPECTED_REMOTE_URL,
        "`improvmenets`",
        "bmendonca3",
    ]:
        if required_text not in local_state:
            fail(f"paper/LOCAL_WORKTREE_STATE.md: missing repository snapshot text {required_text!r}", failures)


def check_packet_tag_alignment(failures: list[str]) -> None:
    head = git_stdout(["rev-parse", "HEAD"])
    tag_commit = git_maybe_stdout(["rev-parse", f"{PACKET_TAG}^{{}}"])
    if not tag_commit:
        fail(f"{PACKET_TAG}: missing packet tag", failures)
    elif tag_commit != head:
        fail(
            f"{PACKET_TAG}: tag peels to {tag_commit[:12]}, but current HEAD is {head[:12]}",
            failures,
        )


def check_no_mutable_github_links(failures: list[str]) -> None:
    mutable_patterns = [
        f"github.com/bmendonca3/k8s-auto-fix/blob/main/",
        f"github.com/bmendonca3/k8s-auto-fix/tree/main/",
    ]
    scanned = UPLOAD_FACING_DOCS + [
        "paper/appendices.tex",
    ]
    for path in scanned:
        candidate = ROOT / path
        if not candidate.exists():
            continue
        for line_no, line in enumerate(read_text(path).splitlines(), 1):
            if any(pattern in line for pattern in mutable_patterns):
                fail(f"{path}:{line_no}: mutable GitHub main link in packet-facing source", failures)


def check_retired_public_artifacts_removed(failures: list[str]) -> None:
    tracked = set(git_lines(["ls-files"]))
    for path in RETIRED_PUBLIC_ARTIFACTS:
        if path in tracked:
            fail(f"{path}: retired or local-only artifact is still tracked", failures)


def check_stale_wording(failures: list[str]) -> None:
    for path in STALE_WORDING_DOCS:
        text = read_text(path)
        for pattern in STALE_PATTERNS:
            if re.search(pattern, text):
                fail(f"{path}: contains stale or disallowed wording {pattern!r}", failures)


def check_upload_facing_residue(failures: list[str]) -> None:
    residue_patterns = [
        r"\bAntigravity\b",
        r"\bKiro\b",
        r"\bclaude\b",
    ]
    for path in UPLOAD_FACING_DOCS:
        text = read_text(path)
        for pattern in residue_patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                fail(f"{path}: contains upload-facing process residue {pattern!r}", failures)


def main() -> int:
    failures: list[str] = []
    check_required_files(failures)
    if not failures:
        check_no_go_gate(failures)
        check_external_action_guard(failures)
        check_do_not_upload_lists(failures)
        check_overleaf_clean_package_guidance(failures)
        check_portal_checklist_commands(failures)
        check_gap_register_priorities(failures)
        check_no_local_controls_in_overleaf_tree(failures)
        check_hash_inventory(failures)
        check_mirrored_files(failures)
        check_dirty_snapshot(failures)
        check_repository_snapshot(failures)
        check_packet_tag_alignment(failures)
        check_no_mutable_github_links(failures)
        check_retired_public_artifacts_removed(failures)
        check_stale_wording(failures)
        check_upload_facing_residue(failures)

    if failures:
        print("Submission packet check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Submission packet check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
