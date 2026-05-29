# Backend

## Install

```powershell
py -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

## Run

```powershell
backend\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

## API

- `GET /api/health`
- `GET /api/videos`
- `POST /api/videos/upload`
- `GET /api/videos/{video_id}`
- `DELETE /api/videos/{video_id}`

## Smoke Test

Start the backend first, then run:

```powershell
backend\.venv\Scripts\python.exe backend\smoke_test.py --file backend_data\sample_upload.mp4
```

If you want to keep the uploaded record for manual inspection:

```powershell
backend\.venv\Scripts\python.exe backend\smoke_test.py --file backend_data\sample_upload.mp4 --keep
```
