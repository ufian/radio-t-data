# Remaining Work Statistics

Generated: 2025-01-25

## Summary

| Category | Tasks | Notes |
|----------|-------|-------|
| Manual Review | 192 | Investigate unknown speakers |
| Voice Matching | 268 | Requires audio comparison |
| **Total Tasks** | **460** | |

### Data in data_clean/

| Speaker Type | Replies | Episodes | Duration |
|--------------|---------|----------|----------|
| SPEAKER_MISATTRIBUTED_* | 135 | 22 | 12 min |
| SPEAKER_XX (00-08) | 14,658 | 208 | 979 min (~16 hours) |
| **Total unresolved** | **14,793** | | |

## Manual Review Tasks by Batch

| Batch | Tasks |
|-------|-------|
| batch_0000_0099.yaml | 2 |
| batch_0100_0199.yaml | 2 |
| batch_0200_0299.yaml | 63 |
| batch_0300_0399.yaml | 38 |
| batch_0400_0499.yaml | 22 |
| batch_0500_0599.yaml | 24 |
| batch_0600_0699.yaml | 34 |
| batch_0700_0799.yaml | 3 |
| batch_0800_0899.yaml | 3 |
| batch_0900_0999.yaml | 1 |

## Voice Matching Tasks by Batch

| Batch | Tasks | Types |
|-------|-------|-------|
| batch_0000_0099.yaml | 6 | Other:6 |
| batch_0100_0199.yaml | 36 | Other:36 |
| batch_0200_0299.yaml | 50 | SPEAKER_XX:32, MISATTRIBUTED:13, Other:5 |
| batch_0300_0399.yaml | 70 | SPEAKER_XX:40, MISATTRIBUTED:19, Other:11 |
| batch_0400_0499.yaml | 51 | SPEAKER_XX:26, MISATTRIBUTED:13, Other:12 |
| batch_0500_0599.yaml | 18 | SPEAKER_XX:15, Other:3 |
| batch_0600_0699.yaml | 26 | SPEAKER_XX:26 |
| batch_0700_0799.yaml | 1 | Other:1 |
| batch_0800_0899.yaml | 8 | SPEAKER_XX:3, Other:5 |
| batch_0900_0999.yaml | 2 | Other:2 |

## Completed Work (this session)

Moved to `cleaning/tasks/completed/`:
- 466 manual_review tasks resolved
- 207 voice_matching tasks resolved

### Applied Changes

| Rule | Replies Changed |
|------|-----------------|
| ELDAR → Gray | 152 |
| ELDAR → Umputun | 74 |
| ELDAR → Bobuk | 57 |
| LAVALE → Ksenks | 67 |
| LAVALE → Marin_k_a | 46 |
| LAVALE → Umputun | 30 |
| LAVALE → Bobuk | 10 |
| PETR → Umputun | 18 |
| PETR → Ksenks | 7 |
| PETR → Bobuk | 8 |
| PETR → Marin_k_a | 6 |
| PETR → Gray | 1 |
| MARIN → Ksenks | 41 |
| Small MISATTRIBUTED → _artifact | 59 |
| **Total** | **576** |

## Next Steps

1. **Voice Matching Priority**: SPEAKER_XX with largest speech blocks
2. **MISATTRIBUTED**: 135 replies in voice_matching batches
3. **Manual Review**: Guest identification for older episodes
