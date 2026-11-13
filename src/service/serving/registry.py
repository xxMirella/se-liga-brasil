"""Registry of serving datasets and the safe hook that pipelines call after loading data."""

import logging
from collections.abc import Callable, Mapping
from datetime import date

from service.serving.builder import DatasetSpec, build_dataset
from service.serving.majority_panorama_document import majority_panorama_spec
from service.serving.person_directory import person_directory_spec
from service.serving.person_profile_snapshot import person_profile_snapshot_spec

logger = logging.getLogger(__name__)

SpecFactory = Callable[[object, date], DatasetSpec]

# name -> factory(connection, as_of) -> DatasetSpec. Empty until P1-B/C/D register datasets.
SERVING_DATASETS: Mapping[str, SpecFactory] = {
    "majority_panorama_document": majority_panorama_spec,
    "person_directory": person_directory_spec,
    "person_profile_snapshot": person_profile_snapshot_spec,
}


def rebuild_serving_datasets(
    connection, as_of: date, registry: Mapping[str, SpecFactory] | None = None
) -> dict[str, str]:
    """Rebuild every registered dataset; one failure never blocks the others or the caller.

    Returns {name: version} for rebuilt datasets and {name: "failed:<ErrorType>"} for failures.
    With an empty registry it issues no query and returns {}.
    """
    outcomes = {}
    for name, factory in (SERVING_DATASETS if registry is None else registry).items():
        try:
            outcomes[name] = build_dataset(connection, factory(connection, as_of), as_of).version
        except Exception as error:
            logger.exception("serving dataset %s kept at its previous release", name)
            outcomes[name] = f"failed:{type(error).__name__}"
    return outcomes
