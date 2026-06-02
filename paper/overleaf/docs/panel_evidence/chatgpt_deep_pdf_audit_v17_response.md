## Resolved table

| Item                                                                   |       Status | PDF evidence                                                                                                                                                                                                                                                   |
| ---------------------------------------------------------------------- | -----------: | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Live-cluster 1,000/1,000 conclusion claim no longer points to Table 11 | **Resolved** | Conclusion now says the live-cluster result is "1,000/1,000 fixture-seeded live-cluster dry-run/live-apply acceptance with zero rollbacks" and points only to `data/live_cluster/results_1k.json`; Table 11 is cited later for other offline/latency metrics.  |
| V16 item 1: 93.54% / "5k supported corpus" mismatch                    | **Resolved** | Conclusion now says "93.54% acceptance on the extended 5k rules snapshot (Table 10)."                                                                                                                                                                          |
| V16 item 2: Table 14 "No-schema / kubectl" contradiction               | **Resolved** | Table 14 now says "No-dry-run" with disabled gate "kubectl."                                                                                                                                                                                                   |
| V16 item 3: Table 4 "single-operation fixes" contradiction             | **Resolved** | Table 4 now says "Rules mode emits deterministic JSON Patch arrays."                                                                                                                                                                                           |
| V16 item 4: unlabeled "42.97 vs. 43.40"                                | **Resolved** | Scheduler text now labels the comparison as "42.97 bandit vs. 43.40 FIFO."                                                                                                                                                                                     |
| V16 item 5: Figure 5 247 vs. 152 mismatch / mistaken FIFO comparison   | **Resolved** | Figure 5 caption says "247 scheduler-arm assignments over a 152-item toy queue," and Section 4.10 matches that wording.                                                                                                                                        |
| V16 item 6: Table 11 LLM-5k latency sample ambiguity                   | **Resolved** | Table 11 row label says "LLM-5k (API-backed; 200-trace latency sample)," and the footnote says LLM latency medians come from 200-manifest traces.                                                                                                              |
| V16 item 7: Table 7 truncated raw error strings / latency ambiguity    | **Resolved** | Table 7 now uses categorical failure labels and states latency medians are reported separately from the 200-manifest trace summaries.                                                                                                                          |
| V16 item 8: Page 7/page 8 awkward P95 sentence break                   | **Resolved** | Page 7 now completes the thought: "Figure 5 shows acceptance near FIFO and a 7.9x P95 wait reduction for top-risk items," before the next paragraph begins.                                                                                                    |

## New blockers

None visible from the PDF. External artifacts remain **NOT INSPECTABLE FROM PDF**.

## Final verdict: SUBMIT / SUBMIT AFTER LIGHT PROOFREAD / HOLD-AND-FIX

**SUBMIT.**
