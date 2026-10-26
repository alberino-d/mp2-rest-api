import io
import json
import logging
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from src import DatasetInfo, DatasetStorage, HealthResponse, setup_logging

setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Processing API", version="1.0.0")
storage = DatasetStorage()

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return {"status": "ok", "version": "1.0.0"}

@app.post("/upload", response_model=DatasetInfo)
async def upload_dataset(file: UploadFile = File(...)):
    if Path(file.filename or "").suffix.lower() != ".csv":
        logger.warning(f"Rejected upload: unsupported file type {file.filename}")
        raise HTTPException(status_code=400, detail="Invalid file type. File must be CSV.")

    try:
            content = await file.read()
            df = pd.read_csv(io.BytesIO(content))
    except (pd.errors.EmptyDataError,pd.errors.ParserError,UnicodeDecodeError) as error:
        logger.warning(f"Cannot parse CSV {file.filename}: {error}")
        raise HTTPException(status_code=400, detail="Cannot parse the uploaded CSV")

    dataset_id = storage.save(df, file.filename)
    metadata = storage.get_metadata(dataset_id)
    logger.info(f"Stored CSV: id={dataset_id}, filename={file.filename}, rows={len(df)}")

    return DatasetInfo(**metadata)

@app.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: int, limit: int = Query(default=100, ge=1)):
    df = storage.get(dataset_id)

    if df is None:
        logger.warning(f"Dataset not found: id={dataset_id}")
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    records = json.loads(df.head(limit).to_json(orient="records"))

    logger.info(f"Retrieved dataset: id={dataset_id}, rows={len(records)}")

    return {
        "id": dataset_id,
        "data": records,
        "total_rows": len(df)
    }
