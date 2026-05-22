import os
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)

raw_dir = "D:/cv/mo_n8n/VietNam_Legal_rag_n8n/data/raw/"
files = ["legal_content.parquet", "legal_metadata.parquet", "legal_relationships.parquet"]

for f in files:
    path = os.path.join(raw_dir, f)
    if os.path.exists(path):
        try:
            # read first 5 rows
            df = pd.read_parquet(path, columns=None)
            print(f"\nFile: {f}")
            print(f"Shape: {df.shape}")
            print("Columns:", list(df.columns))
            print("First row sample:")
            print(df.iloc[0].to_dict())
            print("-" * 50)
        except Exception as e:
            print(f"Error reading {f}: {e}")
    else:
        print(f"File not found: {path}")
