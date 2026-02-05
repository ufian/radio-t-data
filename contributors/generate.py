#!/usr/bin/env python3
"""Generate contributors JSON with speaker stats per episode.

Run from repository root:
    .venv/bin/python contributors/generate.py
"""

import json
import os
from collections import defaultdict

DATA_CLEAN_DIR = "data_clean"
DATA_DIR = "data"  # For desc files with dates
OUTPUT_FILE = "contributors/episodes.json"

# Skip these "speakers" - not real contributors
SKIP_SPEAKERS = {"_ad", "_artifact", "_artifact_99", "SPEAKER_99"}


def is_valid_speaker(author):
    """Check if speaker should be included."""
    if not author:
        return False
    if author in SKIP_SPEAKERS:
        return False
    if author.startswith("SPEAKER_"):
        return False
    if author.startswith("_"):
        return False
    return True


HOSTS = {"Umputun", "Bobuk", "Gray", "Ksenks", "Alek.sys", "Marin_k_a", "Olyapka", "Lavale"}
FEMALE_HOSTS = {"Ksenks", "Marin_k_a", "Olyapka", "Lavale"}
FORMER_HOSTS = {"Olyapka", "Lavale", "Marin_k_a"}


def get_speaker_type(author):
    """Determine speaker type: host, caller, or guest."""
    if author in HOSTS:
        return "host"
    if author.startswith("Caller"):
        return "caller"
    return "guest"


def is_female(author):
    """Check if speaker is female (for badge text)."""
    return author in FEMALE_HOSTS


def is_former_host(author):
    """Check if speaker is a former host."""
    return author in FORMER_HOSTS


def main():
    episodes_data = []

    # Get all episode directories
    episode_dirs = sorted([d for d in os.listdir(DATA_CLEAN_DIR) if d.isdigit()], key=int)

    for ep_num in episode_dirs:
        cc_file = os.path.join(DATA_CLEAN_DIR, ep_num, f"{ep_num}_cc.json")
        desc_file = os.path.join(DATA_DIR, ep_num, f"{ep_num}_desc.json")

        if not os.path.exists(cc_file):
            continue

        # Load CC data
        with open(cc_file) as f:
            cc_data = json.load(f)
        subs = cc_data.get("subs", []) if isinstance(cc_data, dict) else cc_data

        # Load description for date
        date = None
        if os.path.exists(desc_file):
            with open(desc_file) as f:
                desc_data = json.load(f)
            date = desc_data.get("date")

        # Calculate speaker durations
        speaker_durations = defaultdict(float)
        for s in subs:
            author = s.get("author", "")
            if is_valid_speaker(author):
                duration = s.get("etime", 0) - s.get("stime", 0)
                if duration > 0:
                    speaker_durations[author] += duration

        # Build episode entry (skip contributors with <90s in this episode)
        contributors = []
        for author, duration in sorted(speaker_durations.items(), key=lambda x: -x[1]):
            if duration >= 90:  # Minimum 90 seconds per episode
                contributors.append({
                    "name": author,
                    "seconds": round(duration, 1),
                    "type": get_speaker_type(author),
                    "female": is_female(author),
                    "former": is_former_host(author)
                })

        episode_entry = {
            "episode": int(ep_num),
            "date": date,
            "contributors": contributors
        }
        episodes_data.append(episode_entry)

    # Sort by episode number
    episodes_data.sort(key=lambda x: x["episode"])

    # Write output
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(episodes_data, f, ensure_ascii=False, indent=2)

    print(f"Generated {OUTPUT_FILE}")
    print(f"Total episodes: {len(episodes_data)}")

    # Summary stats
    all_contributors = defaultdict(lambda: {"episodes": 0, "total_seconds": 0})
    for ep in episodes_data:
        for c in ep["contributors"]:
            all_contributors[c["name"]]["episodes"] += 1
            all_contributors[c["name"]]["total_seconds"] += c["seconds"]

    # Count by type
    hosts = {k: v for k, v in all_contributors.items() if get_speaker_type(k) == "host"}
    callers = {k: v for k, v in all_contributors.items() if get_speaker_type(k) == "caller"}
    guests = {k: v for k, v in all_contributors.items() if get_speaker_type(k) == "guest"}

    print(f"Total unique contributors: {len(all_contributors)}")
    print(f"  - Hosts: {len(hosts)}")
    print(f"  - Guests: {len(guests)}")
    print(f"  - Callers: {len(callers)}")

    print("\nTop 10 by total time:")
    for name, stats in sorted(all_contributors.items(), key=lambda x: -x[1]["total_seconds"])[:10]:
        hours = stats["total_seconds"] / 3600
        print(f"  {name}: {hours:.1f}h across {stats['episodes']} episodes")


if __name__ == "__main__":
    main()
