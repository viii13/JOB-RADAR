import sqlite3
from pathlib import Path
import pandas as pd

db_path = Path(__file__).resolve().parents[1] / "data" / "jobradar.db"
conn = sqlite3.connect(str(db_path))
c = conn.cursor()

print("--- SQLITE JOBRADAR.DB AUDIT ---")
print("Sources columns:", [r[1] for r in c.execute("PRAGMA table_info(sources)").fetchall()])
for row in c.execute("SELECT * FROM sources").fetchall():
    print("Source:", row)

total_jobs = c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
print("Total rows in jobs table:", total_jobs)

print("\nBreakdown by source_id:")
for row in c.execute("SELECT source_id, COUNT(*) FROM jobs GROUP BY source_id"):
    print(" ", row)

print("\nUnique source_job_id in jobs:", c.execute("SELECT COUNT(DISTINCT source_job_id) FROM jobs").fetchone()[0])
print("Unique identity_key in jobs:", c.execute("SELECT COUNT(DISTINCT identity_key) FROM jobs").fetchone()[0])

print("\nIngestion runs:")
print("Ingestion runs columns:", [r[1] for r in c.execute("PRAGMA table_info(ingestion_runs)").fetchall()])
for row in c.execute("SELECT * FROM ingestion_runs").fetchall():
    print(" ", row)

conn.close()

print("\n--- PROCESSED CSV AUDIT ---")
cleaned_csv = Path(__file__).resolve().parents[1] / "data" / "processed" / "cleaned_indian_job_market_2025.csv"
if cleaned_csv.exists():
    df = pd.read_csv(cleaned_csv, usecols=["jobId"], dtype={"jobId": str})
    print("Rows in cleaned_indian_job_market_2025.csv:", len(df))
    print("Unique jobIds in cleaned CSV:", df["jobId"].nunique())
    print("Duplicate jobIds in cleaned CSV:", len(df) - df["jobId"].nunique())
    dups = df[df.duplicated(subset=["jobId"], keep=False)]
    print("Duplicate jobId values:", dups["jobId"].tolist())
