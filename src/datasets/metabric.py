"""METABRIC dataset loader."""

from .base import BaseDataset


class METABRICDataset(BaseDataset):
    """Load METABRIC using the primary schema in ``config/datasets.yaml``."""

    def __init__(self, data_path: str | None = None) -> None:
        super().__init__(data_path=data_path, dataset_name="metabric")
