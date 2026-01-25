# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a data repository containing transcripts and metadata for the Radio-T podcast (a Russian-language tech podcast). The repository contains structured data files for 992 episodes (0-991) plus analysis results for participant identification.

## Data Structure

### Episode Data (`data/{N}/`)

Each episode is stored in `data/{N}/` where N is the episode number, containing four files:

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

### Haiku Analysis Data (`haiku_analysis/`)

Intermediate data from Claude Haiku-based name extraction:
- `batch_*.json` - 66 batches of guests for analysis
- `haiku_batch_*.json` - Results from Haiku analysis
- `guests_to_analyze.json` - Full list of guests for processing

## Speaker Attribution

### Known Regular Hosts
| Name | Episodes | Role |
|------|----------|------|
| Umputun | 984 | Main host |
| Bobuk | 853 | Co-host |
| Gray | 739 | Co-host |
| Ksenks | 468 | Co-host |
| Alek.sys | 526 | Co-host |

### Speaker ID Conventions
- Named speakers (Umputun, Bobuk, etc.) - identified hosts/guests
- `Guest`, `Guest1`-`Guest29` - unidentified guests from older episodes
- `SPEAKER_00`-`SPEAKER_08` - auto-transcribed speakers (may be guests or misattributed hosts)
- `SPEAKER_99` - typically audio artifacts, jingles, or sound effects
- `_ad` - advertisement segments

### Identification Statistics
- Total guest entries analyzed: 1,303
- Identified: 292 (66% of real guests)
- Unidentified real guests: 151 (34%)
- Filtered noise/artifacts: 860

## Data Characteristics

- Episode numbers start at 0 (pilot from 2006-08-27) and continue to 991+
- All text content is in Russian
- Timestamps in CC files are in seconds with centisecond precision
- SSA files use Aegisub-compatible format
- Speaker variations normalized: `Grey`→`Gray`, `Alex.sys`→`Alek.sys`
