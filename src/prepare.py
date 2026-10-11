import os
import yaml
import pandas as pd


def prepare() -> None:
    with open("params.yaml") as f:
        params = yaml.safe_load(f)["train"]

    RAW_DATA_DIR = params["data"]["raw_data_dir"]
    OUT_DATA_DIR = params["data"]["processed_data_dir"]
    RANDOM_STATE = params["random_state"]

    os.makedirs(OUT_DATA_DIR, exist_ok=True)

    for split in ["train", "test"]:
        print(f"Processing '{split}' split...")

        input_file = os.path.join(RAW_DATA_DIR, f"{split}.csv");
        output_file = os.path.join(OUT_DATA_DIR, f"{split}.csv");

        processed_split = (
            pd.read_csv(input_file)
                .drop_duplicates()
                .dropna()
                .sample(frac=1, random_state=RANDOM_STATE)
        )
        processed_split.to_csv(output_file, index=False)

        print(f"'{split}' samples: {len(processed_split)}")


if __name__ == "__main__":
    prepare()
