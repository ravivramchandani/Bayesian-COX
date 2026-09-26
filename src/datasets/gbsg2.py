"""German Breast Cancer Study Group 2 (GBSG2) dataset loader."""

from .base import BaseDataset


class GBSG2Dataset(BaseDataset):
    """Load GBSG2 using the primary schema in ``config/datasets.yaml``."""

    def __init__(self, data_path: str | None = None) -> None:
        super().__init__(data_path=data_path, dataset_name="gbsg2")
