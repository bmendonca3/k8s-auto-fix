
import re

def fix_overfull_hbox(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # 1. Fix Discussion URL/Path
    # Pattern: \texttt{e4af5...} -> \url{e4af5...}
    # Pattern: \texttt{archives/...} -> \url{archives/...}
    content = content.replace(r'\texttt{e4af5efa7b0a52d7b7e58d76879b0060b354af27}', r'\url{e4af5efa7b0a52d7b7e58d76879b0060b354af27}')
    content = content.replace(r'\texttt{archives/k8s-auto-fix-evidence-20251020.tar.gz}', r'\url{archives/k8s-auto-fix-evidence-20251020.tar.gz}')

    # 2. Fix Appendix B (Risk Score Example)
    # Replaces specific \texttt paths with \url
    paths_to_fix = [
        "data/batch_runs/detections_grok200.json",
        "data/policy_metrics_grok200.json",
        "data/batch_runs/patches_grok200.json",
        "data/batch_runs/verified_grok200.json"
    ]
    for path in paths_to_fix:
        content = content.replace(r'\texttt{' + path + '}', r'\url{' + path + '}')

    # 3. Fix Appendix D and E tables (Artifact Index & Manifest)
    # The tables use >{\ttfamily...}p{...} which forces ttfamily.
    # We want to wrap the content in \url{...}.
    # The content in the tex file has escaped underscores (e.g. data/live\_cluster/results\_1k.json)
    # We need to match these lines in the tabular environments.

    # Strategy: Find the lines inside the tabularx environments in the appendices and wrap the first column content in \url{...}
    # However, replacing strictly by string match is safer if we know the content.

    # List of artifacts from the grep output + known others
    # We need to handle the escaped underscores in the source file.
    artifacts = [
        r"data/live\_cluster/results\_1k.json",
        r"data/live\_cluster/summary\_1k.csv",
        r"data/batch\_runs/grok\_5k/metrics\_grok5k.json",
        r"data/batch\_runs/grok\_5k/\\allowbreak metrics\_grok5k.json", # Special case in App D
        r"data/batch\_runs/grok\_full/metrics\_grok\_full.json",
        r"data/batch\_runs/grok200\_latency\_summary.csv",
        r"data/batch\_runs/verified\_grok200\_latency\_summary.csv",
        r"data/eval/significance\_tests.json",
        r"data/eval/table4\_counts.csv",
        r"data/eval/table4\_with\_ci.csv",
        r"data/scheduler/fairness\_metrics.json",
        r"data/scheduler/metrics\_schedule\_sweep.json",
        r"data/risk/risk\_calibration.csv",
        r"data/metrics\_schedule\_compare.json",
        r"data/grok\_failure\_analysis.csv"
    ]

    for artifact in artifacts:
        # We want to replace "artifact" with "\url{artifact_unescaped}"
        # But wait, if we use \url, we should pass the unescaped string (no backslashes before underscores)
        # OR, if we use \url, it treats it as verbatim, so if we pass "data/live\_cluster...", it might print the backslash.
        # Standard \url{...} usage expects raw characters.
        # So we should strip the backslashes from the replacement string.

        # Remove \\allowbreak for the replacement url
        clean_artifact_for_url = artifact.replace(r'\_', '_').replace(r'\\allowbreak ', '')

        # The replacement: \url{clean_artifact_for_url}
        # Note: We must be careful not to double-wrap if run multiple times, but we assume single run.

        # We only want to replace it if it's NOT already wrapped in \url.
        # Regex lookbehind is hard, but we can just replace string literals.

        # Search for the artifact string.
        # Note: The file content has "data/live\_cluster/results\_1k.json".

        # If we replace `data/live\_cluster...` with `\url{data/live_cluster...}`
        replacement = r'\url{' + clean_artifact_for_url + '}'

        # Special handling for the split line in Appendix D
        if "allowbreak" in artifact:
             # The source has: data/batch_runs/grok_5k/\allowbreak metrics_grok5k.json
             # We want to replace the whole thing with \url{...}
             pass

        content = content.replace(artifact, replacement)

    # Also fix Appendix F (Corpus)
    # data/manifests/artifacthub/ -> \url{...}
    # docs/appendix_corpus.md -> \url{...}
    # data/manifests/001.yaml -> \url{...}
    # 002.yaml -> \url{...}

    corpus_fixes = [
        (r'docs / appendix _ corpus . md', r'\url{docs/appendix_corpus.md}'), # This looks like what grep output showed (badness 10000 log)
        # Wait, the log showed expanded text. The file has escaped text.
        (r'docs/appendix\_corpus.md', r'\url{docs/appendix_corpus.md}'),
        (r'data/manifests/001.yaml', r'\url{data/manifests/001.yaml}'),
        (r'002.yaml', r'\url{002.yaml}') # Be careful with this short match
    ]

    for old, new in corpus_fixes:
        # Check if already wrapped
        if r'\url{' + old not in content and old in content:
             # Special check for 002.yaml to avoid false positives?
             # It appears as: "data/manifests/001.yaml and 002.yaml"
             content = content.replace(old, new)

    with open(filepath, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    fix_overfull_hbox('paper/access.tex')
