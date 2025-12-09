
import re

def fix_appendix_b(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Replacements for Appendix B
    # Note: Source has escaped underscores "\_"
    replacements = [
        (r'\texttt{data/batch\_runs/detections\_grok200.json}', r'\url{data/batch_runs/detections_grok200.json}'),
        (r'\texttt{data/policy\_metrics\_grok200.json}', r'\url{data/policy_metrics_grok200.json}'),
        (r'\texttt{data/batch\_runs/patches\_grok200.json}', r'\url{data/batch_runs/patches_grok200.json}'),
        (r'\texttt{data/batch\_runs/verified\_grok200.json}', r'\url{data/batch_runs/verified_grok200.json}')
    ]

    for old, new in replacements:
        content = content.replace(old, new)

    # Inject \sloppy after \appendices
    if r'\appendices' in content and r'\appendices\n\n\sloppy' not in content:
        content = content.replace(r'\appendices', r'\appendices' + '\n' + r'\sloppy')

    with open(filepath, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    fix_appendix_b('paper/access.tex')
