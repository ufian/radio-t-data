# Remaining Work Statistics

Generated: 2025-01-25 (updated)

## Summary

| Category | Tasks | Notes |
|----------|-------|-------|
| Manual Review | 139 | Investigate unknown speakers |
| Voice Matching | 268 | Requires audio comparison |
| **Total Tasks** | **407** | |

### Data in data_clean/

| Speaker Type | Replies | Episodes | Duration |
|--------------|---------|----------|----------|
| SPEAKER_MISATTRIBUTED_* | 135 | 22 | 12 min |
| SPEAKER_XX (00-09) | 14,205 | 154 | 968 min (~16 hours) |
| **Total unresolved** | **14,340** | | |

## Session Progress

### This Session Applied

| Rule | Replies |
|------|---------|
| SPEAKER_0X → Umputun | 248 |
| SPEAKER_0X → Bobuk | 86 |
| SPEAKER_0X → Gray | 60 |
| SPEAKER_0X → Marin_k_a | 9 |
| SPEAKER_0X → Ksenks | 6 |
| SPEAKER_0X → Alek.sys | 7 |
| Short artifacts → _artifact | 37 |
| **Subtotal (context)** | **453** |

### Previous Session Applied

| Rule | Replies |
|------|---------|
| MISATTRIBUTED_ELDAR → hosts | 283 |
| MISATTRIBUTED_LAVALE → hosts | 153 |
| MISATTRIBUTED_PETR → hosts | 40 |
| MISATTRIBUTED_MARIN → Ksenks | 41 |
| Small MISATTRIBUTED → _artifact | 59 |
| **Subtotal** | **576** |

**Total this session: 1,029 replies fixed**

## Remaining Manual Review by Type

| Type | Tasks | Description |
|------|-------|-------------|
| SPEAKER_0X | ~55 | Need voice matching (low context confidence) |
| Guest | 19 | Old episodes (ep34-202) - identify guests |
| confirm_or_reject | ~65 | Short replies - verify or artifact |

## Next Steps

1. **Voice Matching**: SPEAKER_XX with substantial speech blocks
2. **Guest Identification**: ep202 has 12 unidentified guests
3. **MISATTRIBUTED**: 135 replies still in voice_matching batches
