"""Dataset-specific feature transformations applied before splitting."""

import numpy as np
import pandas as pd


class FeatureEngineer:
    """Applies log transforms and clinical interaction terms."""

    def __init__(self, dataset_name: str):
        self.dataset_name = dataset_name.lower()

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df_out = df.copy()

        if self.dataset_name == "gbsg2":
            for col, name in [
                ("pnodes", "log_pnodes"),
                ("progrec", "log_progrec"),
                ("estrec", "log_estrec"),
            ]:
                if col in df_out.columns:
                    df_out[name] = np.log1p(df_out[col])

            if "age" in df_out.columns and "horTh" in df_out.columns:
                hor_val = df_out["horTh"].apply(
                    lambda x: 1 if str(x).lower() in ("yes", "1") else 0
                )
                df_out["age_x_horTh"] = df_out["age"] * hor_val

        elif self.dataset_name == "whas500":
            if "age" in df_out.columns and "chf" in df_out.columns:
                df_out["age_x_chf"] = df_out["age"] * df_out["chf"].astype(float)
            if "bmi" in df_out.columns:
                df_out["bmi_low"] = (df_out["bmi"] < 18.5).astype(float)

        elif self.dataset_name == "metabric":
            if "lymph_nodes_examined_positive" in df_out.columns:
                df_out["log_lymph_nodes"] = np.log1p(
                    df_out["lymph_nodes_examined_positive"]
                )
            if "age_at_diagnosis" in df_out.columns and "tumor_stage" in df_out.columns:
                df_out["age_x_stage"] = (
                    df_out["age_at_diagnosis"] * df_out["tumor_stage"]
                )

        return df_out
