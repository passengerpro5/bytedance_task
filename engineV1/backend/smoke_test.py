from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import uuid
from pathlib import Path
from urllib import error, request


def build_multipart_body(field_name: str, file_path: Path) -> tuple[bytes, str]:
    boundary = f"----CodexBoundary{uuid.uuid4().hex}"
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    file_bytes = file_path.read_bytes()

    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        (
            f'Content-Disposition: form-data; name="{field_name}"; '
            f'filename="{file_path.name}"\r\n'
        ).encode("utf-8"),
        f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"),
        file_bytes,
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]

    return b"".join(parts), boundary


def http_json(method: str, url: str, body: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[int, object]:
    req = request.Request(url=url, data=body, method=method)

    for key, value in (headers or {}).items():
        req.add_header(key, value)

    try:
        with request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {payload}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Connection failed: {exc.reason}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test for backend upload flow.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Backend base URL. Default: http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Path to a local mp4/mov file used for upload testing.",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep the uploaded record instead of deleting it after the test.",
    )
    args = parser.parse_args()

    file_path = Path(args.file).resolve()

    if not file_path.exists():
        print(f"[FAIL] File not found: {file_path}")
        return 1

    print(f"[INFO] Using file: {file_path}")

    status, health_payload = http_json("GET", f"{args.base_url}/api/health")
    print(f"[PASS] health: HTTP {status} -> {health_payload}")

    body, boundary = build_multipart_body("files", file_path)
    upload_status, upload_payload = http_json(
        "POST",
        f"{args.base_url}/api/videos/upload",
        body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    print(f"[PASS] upload: HTTP {upload_status}")
    print(json.dumps(upload_payload, ensure_ascii=False, indent=2))

    items = upload_payload.get("items", [])
    if not items:
        print("[FAIL] Upload returned no items.")
        return 1

    video_id = items[0]["id"]
    detail_status, detail_payload = http_json("GET", f"{args.base_url}/api/videos/{video_id}")
    print(f"[PASS] detail: HTTP {detail_status}")
    print(json.dumps(detail_payload, ensure_ascii=False, indent=2))

    list_status, list_payload = http_json("GET", f"{args.base_url}/api/videos")
    print(f"[PASS] list: HTTP {list_status}, count={len(list_payload.get('items', []))}")

    if not args.keep:
        delete_status, delete_payload = http_json("DELETE", f"{args.base_url}/api/videos/{video_id}")
        print(f"[PASS] delete: HTTP {delete_status} -> {delete_payload}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
