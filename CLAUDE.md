# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a data repository containing transcripts and metadata for the Radio-T podcast (a Russian-language tech podcast). The repository contains structured data files for 992 episodes (0-991) plus analysis results for participant identification.

## Data Structure

### Episode Data (`data/{N}/`)

Each episode is stored in `data/{N}/` where N is the episode number, containing four files.

**Note:** `data_clean/{N}/` contains cleaned versions with corrected speaker attributions. Always use `data_clean/` for analysis; `data/` contains original unmodified transcripts.

Files in each episode directory:

- **`{N}_cc.json`** - Closed captions/transcription with speaker attribution
  - Array of `subs` with `id`, `issue`, `author`, `stime`/`etime` (seconds), `text`
  - Known speakers: Umputun, Bobuk, Gray, Ksenks, Alek.sys, and guests

- **`{N}_desc.json`** - Episode metadata
  - `issue`, `date`, `audio` (CDN URL), `cover` (image URL), `start_time` (unix timestamp)
  - `topics` array with `title`, `links`, `time` (HH:MM:SS format)

- **`{N}_chat.json`** - Live chat messages during broadcast
  - Array of `chat` with `author_type` (listener/bot/host), `author_nickname`, `author_name`, `datetime`, `text`

- **`{N}_cc.ssa`** - SubStation Alpha subtitle format for video players

### Participant Analysis Results

- **`participants.md`** - List of 20 known regular participants with statistics
- **`all_identified_guests.json`** - 292 identified guests (JSON format)
- **`all_identified_guests.md`** - Same data in Markdown table format
- **`final_unidentified_guests.json`** - 151 unidentified guests requiring manual review
- **`final_unidentified_guests.md`** - Same with context for identification

### Analysis Scripts (`scripts/`)

- `analyze_participants.py` - Main script for participant extraction
- `extract_names.py` - Regex-based name extraction from context
- `filter_real_guests.py` - Filters noise/artifacts from real guests
- `analyze_speakers_deep.py` - Deep analysis of SPEAKER_* entries

### Cleaning System (`cleaning/`)

- `clean.py` - Main cleaning script, applies rules from configs
- `generate_batches.py` - Generates batches for community review
- `people.yaml` - Registry of hosts and guests with aliases
- `configs/` - YAML configs with cleaning rules
- `batches/` - Batches for manual review by community
- `tasks/manual_review/` - Tasks requiring human decision (confirm/reject/investigate)
- `tasks/voice_matching/` - Tasks requiring audio comparison to identify speaker

## Running Python Scripts

Use the virtual environment in `.venv/`:

```bash
.venv/bin/python cleaning/clean.py
.venv/bin/python cleaning/generate_batches.py --author EldarMurtazin
```

Or activate the environment first:

```bash
source .venv/bin/activate
python cleaning/clean.py
```

### Inline Python Code

For quick Python snippets, write code to a temp file and execute:

```bash
# Write code to temp file
cat > /tmp/claude_script.py << 'PYEOF'
# your code here
PYEOF

# Run it
.venv/bin/python /tmp/claude_script.py
```

This avoids permission prompts for heredoc execution.

### Haiku Analysis Data (`haiku_analysis/`)

Intermediate data from Claude Haiku-based name extraction:
- `batch_*.json` - 66 batches of guests for analysis
- `haiku_batch_*.json` - Results from Haiku analysis
- `guests_to_analyze.json` - Full list of guests for processing

## Speaker Attribution

### Known Regular Hosts
| Name | Episodes | Role | Active Period |
|------|----------|------|---------------|
| Umputun | 984 | Main host | All episodes |
| Bobuk | 853 | Co-host | All episodes |
| Gray | 739 | Co-host | All episodes |
| Marin_k_a | ~200 | Co-host (female) | ~ep200-400 |
| Ksenks | 468 | Co-host (female) | ep300+ (main female host after ~ep400) |
| Alek.sys | 526 | Co-host | ep400+ |

**Note:** Marin_k_a and Ksenks overlap in episodes ~300-400. After ep400, Ksenks is the primary female host.

### Speaker ID Conventions
- Named speakers (Umputun, Bobuk, etc.) - identified hosts/guests
- `Guest`, `Guest1`-`Guest29` - unidentified guests from older episodes
- `SPEAKER_00`-`SPEAKER_08` - auto-transcribed speakers (may be guests or misattributed hosts)
- `SPEAKER_99` - typically audio artifacts, jingles, or sound effects
- `SPEAKER_MISATTRIBUTED_X` - speaker incorrectly assigned to person X who didn't participate in episode
- `_ad` - advertisement segments
- `_artifact` - audio noise, jingles, short unidentifiable fragments

### Identification Statistics
- Total guest entries analyzed: 1,303
- Identified: 292 (66% of real guests)
- Unidentified real guests: 151 (34%)
- Filtered noise/artifacts: 860

## Speaker Attribution Resolution

### Decision Logic for SPEAKER_MISATTRIBUTED_X

When a speaker is marked as `SPEAKER_MISATTRIBUTED_X`, it means X was incorrectly assigned (X didn't participate in that episode). Resolution steps:

1. **Check episode participation** - verify X is not in the episode's host list
2. **Analyze context** - who speaks immediately before/after the misattributed replies
3. **If same host before AND after** (confidence ≥40%) → assign to that host
4. **If different hosts or unclear** → send to voice_matching

### Decision Logic for SPEAKER_XX

1. **If SPEAKER_XX has few replies + known host has many** → likely segmentation error, merge with host
2. **If SPEAKER_XX has many replies + female host = 0** → likely unrecognized Ksenks/Marin_k_a
3. **If SPEAKER_XX has substantial speech and unclear** → send to voice_matching
4. **Short replies < 10 sec without context** → mark as `_artifact`

### Female Host Attribution (Marin_k_a vs Ksenks)

- Episodes 200-300: Marin_k_a is primary female host
- Episodes 300-400: Both may appear, check episode introduction (first 60-90 sec)
- Episodes 400+: Ksenks is primary; if Marin_k_a appears with 0 speech, it's likely misrecognized Ksenks
- Verify by searching for name mentions ("Ксюш", "Марин") in episode text

### Context Analysis Method

To determine who a misattributed speaker really is:
```python
# Count who speaks before/after misattributed replies
for each misattributed_reply:
    before = previous_reply.author
    after = next_reply.author
    if before in hosts: context[before] += 1
    if after in hosts: context[after] += 1

# If one host dominates context (≥40%), assign to them
likely_speaker = max(context, key=context.get)
confidence = context[likely_speaker] / (total_replies * 2)
```

## Data Characteristics

- Episode numbers start at 0 (pilot from 2006-08-27) and continue to 991+
- All text content is in Russian
- Timestamps in CC files are in seconds with centisecond precision
- SSA files use Aegisub-compatible format
- Speaker variations normalized: `Grey`→`Gray`, `Alex.sys`→`Alek.sys`
