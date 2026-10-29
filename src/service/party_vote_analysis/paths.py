"""Filesystem layout of the roll-call party model (data/ is not versioned)."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
VOTES_DIRECTORY = PROJECT_ROOT / "data" / "political-orientation" / "party-model" / "votes"
RAW_DIRECTORY = VOTES_DIRECTORY / "raw"
NORMALIZED_DIRECTORY = VOTES_DIRECTORY / "normalized"
