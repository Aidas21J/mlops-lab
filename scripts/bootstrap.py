import os
import shutil
import yaml
from datasets import load_dataset


def main():
    with open("params.yaml") as f:
        params = yaml.safe_load(f)["train"]["data"]

    REPO_ID = params["repo_id"]
    COMMIT_HASH = params["commit_hash"]
    OUTPUT_DIR = params["raw_data_dir"]

    if os.path.exists(OUTPUT_DIR) and os.path.isdir(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)

    os.makedirs(OUTPUT_DIR)

    print(f"Pulling dataset '{REPO_ID}' at commit '{COMMIT_HASH}'...")
    dataset = load_dataset(REPO_ID, revision=COMMIT_HASH)

    for split_name, split_data in dataset.items():
        csv_path = os.path.join(OUTPUT_DIR, f"{split_name}.csv")
        print(f"Saving '{split_name}' split to {csv_path}...")

        df = split_data.to_pandas()
        df.to_csv(csv_path, index=False)

    print("Dataset successfully pulled, converted, and saved.")


if __name__ == "__main__":
    main()
