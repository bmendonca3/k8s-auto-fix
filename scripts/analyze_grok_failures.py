import json
import os
import pandas as pd
import numpy as np
from collections import Counter

def analyze_grok_failures(data_dir, patches_file):
    """
    Analyzes the Grok verification data to extract failure causes and latencies,
    and generate a CSV and a LaTeX table.

    Args:
        data_dir (str): The directory containing the 'verified_grok5k_batch_*.json' files.
        patches_file (str): The path to the 'patches.json' file.
    """
    all_failures = []
    all_latencies = []

    # Read all verified files
    for filename in sorted(os.listdir(data_dir)):
        if filename.startswith("verified_grok5k_batch_") and filename.endswith(".json"):
            filepath = os.path.join(data_dir, filename)
            with open(filepath, 'r') as f:
                data = json.load(f)
                for entry in data:
                    if not entry["accepted"]:
                        all_failures.append(entry)

    # Read patches file to get latencies
    with open(patches_file, 'r') as f:
        patches_data = json.load(f)
        for patch in patches_data:
            all_latencies.append(patch.get("total_latency_ms", 0))


    failure_causes = []
    for failure in all_failures:
        if failure["errors"]:
            # Sanitize and truncate the error messages
            sanitized_errors = []
            for error in failure["errors"]:
                error = error.replace('\n', ' ').replace('_', '\\_').replace('%', '\\%').replace('&', '\\&')
                error = error.replace('#', '\\#').replace('$', '\\$').replace('{', '\\{').replace('}', '\\}')
                if len(error) > 100:
                    error = error[:100] + "..."
                sanitized_errors.append(error)
            failure_causes.extend(sanitized_errors)
        else:
            failure_causes.append("Unknown error")

    failure_counts = Counter(failure_causes)

    # Create a DataFrame for the CSV
    df = pd.DataFrame(failure_counts.items(), columns=["Failure Cause", "Count"])
    df = df.sort_values(by="Count", ascending=False)
    csv_path = os.path.join("data", "grok_failure_analysis.csv")
    df.to_csv(csv_path, index=False)
    print(f"Generated failure analysis CSV at: {csv_path}")

    # Calculate latency stats
    p50_latency = np.percentile(all_latencies, 50)
    p95_latency = np.percentile(all_latencies, 95)


    # Create a LaTeX table using tabularx for wrapping text
    latex_table = "\\begin{table}[h!]\n"
    latex_table += "\\centering\n"
    latex_table += "\\caption{Top 10 Grok/xAI Failure Causes and Latencies}\n"
    latex_table += "\\label{tab:grok_failures}\n"
    latex_table += "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}X r}\n"
    latex_table += "\\toprule\n"
    latex_table += "\\textbf{Failure Cause} & \\textbf{Count} \\\\\n"
    latex_table += "\\midrule\n"
    for cause, count in failure_counts.most_common(10):
        latex_table += f"{cause} & {count} \\\\\n"
    latex_table += "\\midrule\n"
    latex_table += f"P50 Latency & {p50_latency:.2f} ms \\\\\n"
    latex_table += f"P95 Latency & {p95_latency:.2f} ms \\\\\n"
    latex_table += "\\bottomrule\n"
    latex_table += "\\end{tabularx}\n"
    latex_table += "\\end{table}\n"

    latex_file_path = "paper/grok_failures_table.tex"
    with open(latex_file_path, "w") as f:
        f.write(latex_table)
    print(f"Generated LaTeX table at: {latex_file_path}")


if __name__ == "__main__":
    analyze_grok_failures("data/batch_runs/grok_5k", "data/patches.json")
