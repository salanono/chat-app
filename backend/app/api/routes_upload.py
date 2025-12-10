# backend/app/api/routes_upload.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pathlib import Path
import uuid

router = APIRouter(prefix="/api", tags=["upload"])

UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # 拡張子
    suffix = Path(file.filename).suffix
    # 適当なファイル名
    new_name = f"{uuid.uuid4()}{suffix}"
    save_path = UPLOAD_DIR / new_name

    try:
        content = await file.read()
        save_path.write_bytes(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存に失敗しました: {e}")

    # フロントに返す URL（/uploads は main.py で mount 済みのはず）
    url = f"/uploads/{new_name}"

    return JSONResponse({"url": url})