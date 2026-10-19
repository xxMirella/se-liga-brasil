"""Daily, idempotent consolidation of verified public voting facts."""

from service.daily_voting_dataset.contracts import DailyDatasetManifest, DailyVotingPartition
from service.daily_voting_dataset.publication import consolidate_daily_votes

__all__ = ["DailyDatasetManifest", "DailyVotingPartition", "consolidate_daily_votes"]
