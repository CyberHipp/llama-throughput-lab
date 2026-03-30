# NEXUS Safe Merge Sequence (work -> main)

## 0) Preconditions
- Clean local repo
- GitHub auth working
- Candidate branch: `work`
- Target branch: `main`

## 1) Sync and inspect
```bash
git fetch --all --prune
git checkout main
git pull --ff-only origin main
git checkout work
git pull --ff-only origin work
git log --oneline --decorate --graph -n 30
```

## 2) Rehearse checks on candidate branch
```bash
git checkout work
make ci
python3 scripts/run_nexus_pipeline.py --query "nexus smoke" --config configs/nexus/default.json
```

## 3) Create merge commit locally (no push yet)
```bash
git checkout main
git merge --no-ff work -m "Merge work: llama-nexus-lab pipeline integration"
```

If conflicts:
- resolve deliberately
- rerun checks

## 4) Post-merge verification
```bash
make ci
python3 -m unittest tests/test_execution_core.py tests/test_nexus_config.py tests/test_nexus_pipeline.py
python3 scripts/security_check.py
```

## 5) Push only after all checks pass
```bash
git push origin main
```

## 6) Rollback procedure (if needed)

### Before push (local only)
```bash
git reset --hard HEAD~1
```

### After push
```bash
# create explicit revert commit
git checkout main
git pull --ff-only origin main
git revert -m 1 <merge_commit_sha>
git push origin main
```

## 7) Evidence to capture in PR/merge notes
- candidate SHA and merged SHA
- `make ci` pass output
- security check output
- one sample nexus artifact triple:
  - answer path
  - receipt path
  - evidence path
