"""Worcester Heart Attack Study (WHAS500) dataset loader."""

from .base import BaseDataset


class WHAS500Dataset(BaseDataset):
    """Load WHAS500 using the primary schema in ``config/datasets.yaml``."""

    def __init__(self, data_path: str | None = None) -> None:
        super().__init__(data_path=data_path, dataset_name="whas500")
