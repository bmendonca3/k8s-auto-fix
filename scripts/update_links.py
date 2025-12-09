import re
import os

repo_base = "https://github.com/bmendonca3/k8s-auto-fix"
files_to_process = ["paper/access.tex", "paper/artifact_manifest_insert.tex"]

def clean_latex_for_url(text):
    # Remove common latex noise from path
    t = text.replace(r"\_", "_")
    t = t.replace(r"\allowbreak", "")
    t = t.replace(r"\ ", "")
    t = t.strip()
    return t

def is_repo_path(path):
    # Heuristic to check if a string looks like a repo path
    prefixes = ["data/", "src/", "docs/", "scripts/", "tests/", "infra/", "configs/", "logs/", "paper/", "Makefile", "ARTIFACTS.md", "README.md"]
    clean = clean_latex_for_url(path)

    if any(clean.startswith(p) for p in prefixes):
        # exclude external urls
        if "http" in clean or "www" in clean:
            return False
        if " " in clean:
             return False
        return True
    return False

def get_url(path):
    clean_path = clean_latex_for_url(path)

    # Handle wildcards: if path has *, link to parent dir
    if "*" in clean_path:
        parts = clean_path.split("/")
        wildcard_index = -1
        for i, part in enumerate(parts):
            if "*" in part:
                wildcard_index = i
                break

        if wildcard_index != -1:
            parent_dir = "/".join(parts[:wildcard_index])
            if not parent_dir:
                return f"{repo_base}/tree/main/"
            return f"{repo_base}/tree/main/{parent_dir}/"

    type_seg = "tree" if clean_path.endswith("/") else "blob"
    return f"{repo_base}/{type_seg}/main/{clean_path}"

def replace_url_command(match):
    content = match.group(1)
    if is_repo_path(content):
        url = get_url(content)
        display_content = clean_latex_for_url(content)
        return f"\\href{{{url}}}{{\\nolinkurl{{{display_content}}}}}"
    return match.group(0)

def replace_texttt_command(match):
    content = match.group(1)
    if is_repo_path(content):
        url = get_url(content)
        return f"\\href{{{url}}}{{\\texttt{{{content}}}}}"
    return match.group(0)

def replace_bare_table_paths(line):
    # Regex for paths at start of line (for tables)
    prefixes = ["data/", "src/", "docs/", "scripts/", "tests/", "infra/", "configs/", "logs/", "ARTIFACTS.md", "Makefile"]
    prefixes.sort(key=len, reverse=True)

    stripped = line.lstrip()
    matched_prefix = None
    for p in prefixes:
        if stripped.startswith(p):
            matched_prefix = p
            break

    if matched_prefix:
        match = re.match(r'^(\s*)([\w\-\./\\]+)(.*)', line)
        if match:
            indent = match.group(1)
            path = match.group(2)
            rest = match.group(3)

            if is_repo_path(path):
                url = get_url(path)
                display_path = clean_latex_for_url(path)
                return f"{indent}\\href{{{url}}}{{\\nolinkurl{{{display_path}}}}}{rest}"
    return line

for filepath in files_to_process:
    if not os.path.exists(filepath):
        continue

    with open(filepath, 'r') as f:
        content = f.read()

    # 1. Replace \url{...}
    content = re.sub(r'\\url\{(.*?)\}', replace_url_command, content)

    # 2. Replace \texttt{...}
    content = re.sub(r'\\texttt\{(.*?)\}', replace_texttt_command, content)

    # 3. Handle bare paths in tables
    new_lines = []
    lines = content.split('\n')
    for line in lines:
        new_lines.append(replace_bare_table_paths(line))

    content = '\n'.join(new_lines)

    with open(filepath, 'w') as f:
        f.write(content)
