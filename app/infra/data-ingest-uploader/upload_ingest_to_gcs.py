from pathlib import Path
from datetime import datetime, timezone
import json
from google.cloud import storage


def upload_file(bucket, local_path: Path, remote_path: str) -> None:
    blob = bucket.blob(remote_path)
    blob.upload_from_filename(str(local_path))
    print("Uploaded", local_path, "->", remote_path)


def main() -> None:
    project_id = "ada26-pulse-project"
    bucket_name = "pulse-demo-bronze"

    # e.g. ingest/2026-04-29T14-00-00Z/
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    prefix = f"ingest/{run_id}"

    base = Path("../../../data/ingest")
    financial = base / "financial_clean.csv"
    sales = base / "sales_marketing_clean.csv"

    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)

    upload_file(bucket, financial, f"{prefix}/financial_clean.csv")
    upload_file(bucket, sales, f"{prefix}/sales_marketing_clean.csv")

    # marker file to trigger downstream pipeline only once both files exist
    marker_blob = bucket.blob(f"{prefix}/ready.json")
    marker_blob.upload_from_string(
        json.dumps(
            {
                "run_id": run_id,
                "tenant_id": "pulse-demo",
                "files": ["financial_clean.csv", "sales_marketing_clean.csv"],
            }
        ),
        content_type="application/json",
    )
    print("Uploaded marker ->", f"{prefix}/ready.json")


if __name__ == "__main__":
    main()
