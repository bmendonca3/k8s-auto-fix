#!/usr/bin/env python3
"""
Stratified sampling of manifests for live-cluster evaluation.

Creates a representative ~200-manifest sample stratified by:
- Policy type distribution (proportional to detections_supported.json)
- Resource kind diversity (Deployment, Pod, Service, etc.)

Outputs:
- data/live_cluster/sampled_batch.txt: List of selected manifest paths
- data/live_cluster/batch/: Directory with copies of sampled manifests
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import shutil
from collections import Counter, defaultdict
from typing import Dict, List, Set, Tuple

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate stratified manifest sample for live-cluster evaluation."
    )
    parser.add_argument(
        "--detections",
        type=pathlib.Path,
        default=pathlib.Path("data/detections_supported.json"),
        help="Detections JSON for policy distribution analysis.",
    )
    parser.add_argument(
        "--manifests-root",
        type=pathlib.Path,
        default=pathlib.Path("data/manifests"),
        help="Root directory containing all manifests.",
    )
    parser.add_argument(
        "--target-size",
        type=int,
        default=200,
        help="Target number of manifests to sample.",
    )
    parser.add_argument(
        "--output-list",
        type=pathlib.Path,
        default=pathlib.Path("data/live_cluster/sampled_batch.txt"),
        help="Output file listing selected manifest paths.",
    )
    parser.add_argument(
        "--output-dir",
        type=pathlib.Path,
        default=pathlib.Path("data/live_cluster/batch"),
        help="Output directory to copy sampled manifests.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1337,
        help="Random seed for reproducible sampling.",
    )
    parser.add_argument(
        "--min-per-policy",
        type=int,
        default=3,
        help="Minimum manifests per policy type (if available).",
    )
    return parser.parse_args()


def load_detections(path: pathlib.Path) -> List[Dict]:
    """Load detections from JSON file."""
    return json.loads(path.read_text())


def get_resource_kind(manifest_path: pathlib.Path) -> Set[str]:
    """Extract resource kinds from a manifest YAML."""
    kinds = set()
    try:
        with manifest_path.open("r", encoding="utf-8") as fh:
            for doc in yaml.safe_load_all(fh):
                if isinstance(doc, dict) and "kind" in doc:
                    kinds.add(doc["kind"])
    except Exception:
        pass
    return kinds


def is_namespace_specific(manifest_path: pathlib.Path) -> bool:
    """
    Check if manifest has hardcoded namespace references (corpus quality issue).
    
    Returns True if the manifest should be excluded from evaluation.
    """
    try:
        with manifest_path.open("r", encoding="utf-8") as fh:
            for doc in yaml.safe_load_all(fh):
                if not isinstance(doc, dict):
                    continue
                
                # Check for hardcoded namespaces (not default, kube-system, or empty)
                namespace = doc.get("metadata", {}).get("namespace")
                if namespace and namespace not in ["default", "kube-system", ""]:
                    # Common environment-specific namespaces to exclude
                    excluded_namespaces = {
                        "prod", "production", "staging", "dev", "development",
                        "boskos", "prow", "openmcp", "nexclipper", "issueflow",
                        "test-pods", "monitoring", "logging"
                    }
                    if namespace.lower() in excluded_namespaces:
                        return True
                    # Exclude any non-generic namespace
                    if not namespace.startswith("live-eval"):  # Allow our test namespaces
                        return True
                
                # Check for deprecated API versions
                api_version = doc.get("apiVersion", "")
                deprecated_versions = ["batch/v1beta1", "extensions/v1beta1", "apps/v1beta1", "apps/v1beta2"]
                if any(dep in api_version for dep in deprecated_versions):
                    return True
                    
    except Exception:
        pass
    
    return False


def stratify_by_policy(
    detections: List[Dict],
    manifests_root: pathlib.Path,
    target_size: int,
    min_per_policy: int,
) -> Tuple[List[pathlib.Path], Dict[str, int]]:
    """
    Stratify manifests by policy distribution.
    
    Returns:
        (sampled_manifests, policy_counts)
    """
    # Build policy -> manifest mapping
    policy_manifests: Dict[str, List[pathlib.Path]] = defaultdict(list)
    manifest_to_policies: Dict[str, List[str]] = defaultdict(list)
    
    for det in detections:
        policy = det.get("policy_id", "unknown")
        manifest_path = det.get("manifest_path")
        if not manifest_path:
            continue
        
        path = pathlib.Path(manifest_path)
        
        # Handle both absolute paths and relative paths
        # If path is already relative to project root, use it as-is
        if not path.is_absolute():
            if not path.exists():
                # Try appending to manifests_root
                alt_path = manifests_root / path
                if alt_path.exists():
                    path = alt_path
        
        if path.exists():
            # Filter out namespace-specific manifests (corpus quality issues)
            if not is_namespace_specific(path):
                policy_manifests[policy].append(path)
                manifest_to_policies[str(path)].append(policy)
    
    # Count policy occurrences
    policy_counts = {p: len(manifests) for p, manifests in policy_manifests.items()}
    total_detections = sum(policy_counts.values())
    
    # Calculate proportional allocation
    policy_targets: Dict[str, int] = {}
    for policy, count in policy_counts.items():
        proportion = count / total_detections
        allocated = max(min_per_policy, int(target_size * proportion))
        policy_targets[policy] = allocated
    
    # Sample manifests per policy
    sampled: Set[str] = set()
    policy_sample_counts: Dict[str, int] = defaultdict(int)
    
    for policy, target in sorted(policy_targets.items(), key=lambda x: -x[1]):
        available = [
            m for m in policy_manifests[policy]
            if str(m) not in sampled
        ]
        
        # Deduplicate manifests (same manifest may match multiple policies)
        to_sample = min(target, len(available))
        selected = random.sample(available, to_sample)
        
        for manifest in selected:
            if str(manifest) not in sampled:
                sampled.add(str(manifest))
                policy_sample_counts[policy] += 1
        
        if len(sampled) >= target_size:
            break
    
    # If we're short, top up with random selection
    if len(sampled) < target_size:
        all_manifests = set()
        for manifests in policy_manifests.values():
            all_manifests.update(str(m) for m in manifests)
        
        remaining = list(all_manifests - sampled)
        needed = target_size - len(sampled)
        if remaining:
            additional = random.sample(remaining, min(needed, len(remaining)))
            sampled.update(additional)
    
    return [pathlib.Path(p) for p in sampled], policy_sample_counts


def analyze_resource_diversity(manifests: List[pathlib.Path]) -> Dict[str, int]:
    """Analyze resource kind distribution in sampled manifests."""
    kind_counts = Counter()
    for manifest in manifests:
        kinds = get_resource_kind(manifest)
        kind_counts.update(kinds)
    return dict(kind_counts)


def sample_additional_from_corpus(
    manifests_root: pathlib.Path,
    selected: List[pathlib.Path],
    target_size: int,
) -> List[pathlib.Path]:
    """
    Top up the sampled manifests using the broader corpus.

    Ensures we can hit larger targets (e.g., 1k) even when the detections
    dataset only covers a subset of manifests.
    """
    needed = target_size - len(selected)
    if needed <= 0:
        return []

    manifests_root = manifests_root.resolve()
    selected_resolved = {p.resolve() for p in selected}
    candidates: List[pathlib.Path] = []

    for candidate in manifests_root.rglob("*.yaml"):
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if resolved in selected_resolved:
            continue
        if is_namespace_specific(candidate):
            continue
        candidates.append(candidate)

    if not candidates:
        return []

    if len(candidates) <= needed:
        return candidates

    return random.sample(candidates, needed)


def write_outputs(
    sampled: List[pathlib.Path],
    output_list: pathlib.Path,
    output_dir: pathlib.Path,
    manifests_root: pathlib.Path,
) -> None:
    """Write sampled manifest list and copy files to output directory."""
    # Write list
    output_list.parent.mkdir(parents=True, exist_ok=True)
    with output_list.open("w", encoding="utf-8") as fh:
        for manifest in sorted(sampled):
            fh.write(f"{manifest}\n")
    
    # Copy manifests
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    root_resolved = manifests_root.resolve()
    
    for idx, manifest in enumerate(sorted(sampled), start=1):
        # Create a unique filename preserving some path structure
        manifest_resolved = manifest.resolve()
        try:
            rel_path = manifest_resolved.relative_to(root_resolved)
        except ValueError:
            rel_path = manifest
        safe_name = str(rel_path).replace("/", "_").replace(" ", "_")
        dest = output_dir / f"{idx:04d}_{safe_name}"
        shutil.copy2(manifest, dest)


def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    
    manifests_root = args.manifests_root.resolve()

    print(f"Loading detections from {args.detections}")
    detections = load_detections(args.detections)
    print(f"  Loaded {len(detections)} detections")
    
    print(f"\nStratifying manifests (target size: {args.target_size})")
    sampled, policy_counts = stratify_by_policy(
        detections,
        manifests_root,
        args.target_size,
        args.min_per_policy,
    )
    print(f"  Sampled {len(sampled)} manifests")

    if len(sampled) < args.target_size:
        print(
            f"  Insufficient coverage from detections (needed {args.target_size}, "
            f"have {len(sampled)}). Falling back to corpus sampling..."
        )
        additional = sample_additional_from_corpus(
            manifests_root,
            sampled,
            args.target_size,
        )
        sampled.extend(additional)
        sampled = sorted({p.resolve(): p for p in sampled}.values())
        print(f"  Added {len(additional)} corpus manifests (total {len(sampled)})")
    
    print(f"\nPolicy distribution:")
    for policy, count in sorted(policy_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  {policy}: {count}")
    if len(policy_counts) > 10:
        print(f"  ... and {len(policy_counts) - 10} more policies")

    print(f"\nResource kind diversity:")
    kinds = analyze_resource_diversity(sampled)
    for kind, count in sorted(kinds.items(), key=lambda x: -x[1])[:10]:
        print(f"  {kind}: {count}")
    if len(kinds) > 10:
        print(f"  ... and {len(kinds) - 10} more kinds")
    
    print(f"\nWriting outputs:")
    write_outputs(sampled, args.output_list, args.output_dir, manifests_root)
    print(f"  Manifest list: {args.output_list}")
    print(f"  Manifest copies: {args.output_dir}/")
    print(f"\nStratified sampling complete!")


if __name__ == "__main__":
    main()
