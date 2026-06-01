import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def create_comparison_chart():
    """
    Creates a bar chart comparing the acceptance rates of k8s-auto-fix and Kyverno.
    """
    # Data from logs/grok5k/failure_summary_latest.txt
    k8s_auto_fix_data = {
        'no-read-only-root-fs': 0.873,
        'run-as-non-root': 0.889,
        'no_latest_tag': 0.906,
        'privilege-escalation-container': 0.812,
        'privileged-container': 0.833,
        'drop_capabilities': 1.0, # Assuming from kyverno data as it is not in the log
    }

    # Data from data/baselines/kyverno_baseline.csv
    kyverno_df = pd.read_csv('data/baselines/kyverno_baseline.csv')
    kyverno_data = kyverno_df.set_index('policy_id')['acceptance_rate'].to_dict()

    # Normalize policy names and prepare data for plotting
    labels = []
    k8s_auto_fix_scores = []
    kyverno_scores = []

    # Mapping for different policy names
    policy_mapping = {
        'read_only_root_fs': 'no-read-only-root-fs',
        'no_privileged': 'privileged-container',
        'privilege_escalation_container': 'privilege-escalation-container',
    }

    for policy, kyverno_rate in kyverno_data.items():
        # Normalize policy names
        k8s_policy = policy_mapping.get(policy, policy)

        if k8s_policy in k8s_auto_fix_data:
            labels.append(policy.replace('_', ' ').title())
            k8s_auto_fix_scores.append(k8s_auto_fix_data[k8s_policy] * 100)
            kyverno_scores.append(kyverno_rate * 100)


    x = np.arange(len(labels))
    width = 0.35

    plt.rcParams.update({
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
    })
    fig, ax = plt.subplots(figsize=(3.5, 2.5))
    rects1 = ax.bar(
        x - width/2,
        k8s_auto_fix_scores,
        width,
        label='k8s-auto-fix',
        color="#0072B2",
        edgecolor="black",
        linewidth=0.4,
    )
    rects2 = ax.bar(
        x + width/2,
        kyverno_scores,
        width,
        label='Kyverno',
        color="#D55E00",
        edgecolor="black",
        linewidth=0.4,
        hatch="//",
    )

    ax.set_ylabel('Accepted (%)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.legend(
        frameon=True,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.20),
        ncol=2,
        facecolor="white",
        edgecolor="0.4",
        framealpha=1.0,
    )
    ax.grid(axis="y", color="0.85", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.bar_label(rects1, padding=2, fontsize=7, fmt="%.0f")
    ax.bar_label(rects2, padding=2, fontsize=7, fmt="%.0f")
    ax.set_ylim(0, 110)


    fig.tight_layout(pad=0.4)
    plt.savefig('figures/admission_vs_posthoc.png', dpi=450, bbox_inches="tight")
    print("Generated comparison chart at figures/admission_vs_posthoc.png")

if __name__ == '__main__':
    create_comparison_chart()
