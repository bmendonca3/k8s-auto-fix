# Live-Cluster Evaluation Status Report

**Generated:** $(date)

## Completed Tasks

### ✓ Phase 1: Validation Run
- **Status:** Complete
- **Duration:** ~30 seconds
- **Results:** 13/13 manifests succeeded (100% dry-run, 100% live-apply)
- **Output:** `data/live_cluster/results_validation.json`, `summary_validation.csv`

### ✓ Phase 2: Stratified Sampling
- **Status:** Complete
- **Sample size:** 200 manifests
- **Policy distribution:** 13 policies covered
- **Resource diversity:** 10 kinds (Deployment, Pod, Service, Job, StatefulSet, etc.)
- **Output:** `data/live_cluster/batch/` (200 manifest files)

### ✓ Phase 3: Kyverno Baseline
- **Status:** Complete
- **Duration:** 2 seconds
- **Results:** 81.22% acceptance (1,038/1,278 detections)
- **Top policies:**
  - set_requests_limits: 81.84%
  - run_as_non_root: 81.82%
  - non_existent_service_account: 81.60%
- **Output:** `data/baselines/kyverno_baseline.csv`

### ✓ Phase 4: Monitoring Infrastructure
- **Status:** Complete
- **Scripts created:**
  - `scripts/monitor_background.py` - Process monitoring with log tailing
  - `scripts/stratify_manifests.py` - Stratified sampling
  - `scripts/finalize_live_cluster_results.py` - Auto-update paper when eval completes

### ✓ Phase 5: Documentation Updates
- **Status:** Partial (Kyverno complete, live-cluster pending results)
- **Updated files:**
  - `paper/access.tex` - Added Kyverno baseline comparison (81.22% vs 78.9%)
  - `docs/eval_upgrade_plan.md` - Updated A1 and added A2.5 for Kyverno baseline
  - Discussion checklist - Marked Kyverno complete, live-cluster in progress

### ✓ Phase 6: Artifact Rebuild
- **Status:** Complete
- **Tests:** 87/87 passed (7.4s)
- **LaTeX compilation:** Success (access.pdf, 1.5 MB)

## In Progress

### ⏳ Phase 2 (continued): Full Live-Cluster Evaluation
- **Status:** Running in background (PID: 59028)
- **Elapsed time:** ~7.5 minutes
- **Estimated progress:** 10-15/200 manifests (~5-7%)
- **Estimated completion:** 2-3 hours at current rate
- **Active namespaces:** 21
- **Log file:** `logs/live_cluster_eval.log` (currently empty - script doesn't log incrementally)

**Performance Analysis:**
- Rate: ~1-2 manifests per minute
- Each manifest requires: namespace creation, dry-run, apply, cleanup
- Cluster overhead: API server latency, resource scheduling

## Pending

### Phase 7: Environment Cleanup
- **Status:** Waiting for live-cluster evaluation to complete
- **Actions:**
  - Delete kind cluster: `kind delete cluster --name auto-fix-cluster`
  - Clean temporary files in `data/live_cluster/batch/`
  - Archive logs to `logs/final_evaluation/`

## Next Steps

### Option 1: Wait for Completion (Recommended)
1. Let the 200-manifest evaluation complete (~2-3h remaining)
2. Run finalization script:
   ```bash
   python scripts/finalize_live_cluster_results.py --wait --pid 59028
   ```
3. This will automatically:
   - Wait for process to complete
   - Read results
   - Update paper with actual statistics
   - Recompile LaTeX
4. Then run cleanup:
   ```bash
   kind delete cluster --name auto-fix-cluster
   ```

### Option 2: Reduce Sample Size (Faster)
1. Kill current process: `kill 59028`
2. Reduce to 50 manifests:
   ```bash
   python scripts/stratify_manifests.py --target-size 50 --seed 1337
   python scripts/run_live_cluster_eval.py --manifests data/live_cluster/batch --output data/live_cluster/results.json --summary data/live_cluster/summary.csv
   ```
3. Complete in ~30-40 minutes

### Option 3: Manual Monitoring
Monitor progress with:
```bash
# Check if still running
ps -p 59028

# Count processed namespaces
kubectl get namespaces | grep live-eval | wc -l

# Monitor in real-time (when complete, results.json will update)
watch -n 30 'ls -lh data/live_cluster/results.json 2>/dev/null || echo "Not ready yet"'
```

## Files Modified

**Created:**
- `scripts/stratify_manifests.py`
- `scripts/monitor_background.py`
- `scripts/finalize_live_cluster_results.py`
- `data/live_cluster/batch/*.yaml` (200 files)
- `data/live_cluster/sampled_batch.txt`
- `data/baselines/kyverno_baseline.csv`
- `logs/live_cluster_eval.log`
- `logs/kyverno_baseline.log`

**Modified:**
- `paper/access.tex` - Kyverno baseline comparison added
- `docs/eval_upgrade_plan.md` - A1 status, A2.5 added

**Pending Update (after eval completes):**
- `paper/access.tex` - Line 286: Live-cluster validation bullet
- `data/live_cluster/results.json`
- `data/live_cluster/summary.csv`



