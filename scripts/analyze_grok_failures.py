import json
import os
import csv
from collections import Counter

def analyze_grok_failures(data_dir):
    """
    Analyzes the Grok verification data to extract failure causes and generate
    a CSV plus LaTeX table.

    Args:
        data_dir (str): The directory containing the 'verified_grok5k_batch_*.json' files.
    """
    all_failures = []

    # Read all verified files
    for filename in sorted(os.listdir(data_dir)):
        if filename.startswith("verified_grok5k_batch_") and filename.endswith(".json"):
            filepath = os.path.join(data_dir, filename)
            with open(filepath, 'r') as f:
                data = json.load(f)
                for entry in data:
                    if not entry["accepted"]:
                        all_failures.append(entry)

    failure_causes = []
    failure_causes_full = []
    for failure in all_failures:
        if failure["errors"]:
            # Sanitize for CSV/LaTeX output; keep an untruncated CSV for audit.
            sanitized_errors = []
            for error in failure["errors"]:
                error = error.replace('\n', ' ').replace('_', '\\_').replace('%', '\\%').replace('&', '\\&')
                error = error.replace('#', '\\#').replace('$', '\\$').replace('{', '\\{').replace('}', '\\}')
                failure_causes_full.append(error)
                if len(error) > 100:
                    error = error[:100] + "..."
                sanitized_errors.append(error)
            failure_causes.extend(sanitized_errors)
        else:
            failure_causes.append("Unknown error")
            failure_causes_full.append("Unknown error")

    failure_counts = Counter(failure_causes)

    csv_path = os.path.join("data", "grok_failure_analysis.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["Failure Cause", "Count"])
        writer.writerows(failure_counts.most_common())
    print(f"Generated failure analysis CSV at: {csv_path}")

    full_counts = Counter(failure_causes_full)
    full_csv_path = os.path.join("data", "grok_failure_analysis_full.csv")
    with open(full_csv_path, "w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["Failure Cause", "Count"])
        writer.writerows(full_counts.most_common())
    print(f"Generated full failure analysis CSV at: {full_csv_path}")

    # Create a LaTeX table using tabularx for wrapping text
    latex_table = "\\begin{table}[h!]\n"
    latex_table += "\\centering\n"
    latex_table += "\\caption{Top 10 Grok/xAI dry-run failure causes}\n"
    latex_table += "\\label{tab:grok_failures}\n"
    latex_table += "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}X r}\n"
    latex_table += "\\toprule\n"
    latex_table += "\\textbf{Failure Cause} & \\textbf{Count} \\\\\n"
    latex_table += "\\midrule\n"
    for cause, count in failure_counts.most_common(10):
        latex_table += f"{cause} & {count} \\\\\n"
    latex_table += "\\bottomrule\n"
    latex_table += "\\end{tabularx}\n"
    latex_table += "\\end{table}\n"

    for latex_file_path in (
        "paper/grok_failures_table.tex",
        "paper/overleaf/paper/grok_failures_table.tex",
    ):
        with open(latex_file_path, "w") as f:
            f.write(latex_table)
        print(f"Generated LaTeX table at: {latex_file_path}")


if __name__ == "__main__":
    analyze_grok_failures("data/batch_runs/grok_5k")
