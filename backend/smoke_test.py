from __future__ import annotations

import argparse
import json
import mimetypes
import uuid
from pathlib import Path
from urllib import error, request


def http_json(method: str, url: str, body: bytes | None = None, headers: dict[str, str] | None = None):
    req = request.Request(url=url, data=body, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with request.urlopen(req, timeout=60) as response:
            payload = response.read().decode("utf-8")
            return response.status, json.loads(payload) if payload else {}
    except error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}") from exc


def http_text(method: str, url: str) -> tuple[int, str, str]:
    req = request.Request(url=url, method=method)
    try:
        with request.urlopen(req, timeout=60) as response:
            payload = response.read().decode("utf-8")
            return response.status, response.headers.get("content-type", ""), payload
    except error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}") from exc


def multipart_body(field_name: str, file_path: Path) -> tuple[bytes, str]:
    boundary = f"----CodexBoundary{uuid.uuid4().hex}"
    mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    return (
        b"".join(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{field_name}"; filename="{file_path.name}"\r\n'.encode(),
                f"Content-Type: {mime}\r\n\r\n".encode(),
                file_path.read_bytes(),
                b"\r\n",
                f"--{boundary}--\r\n".encode(),
            ]
        ),
        boundary,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8766")
    parser.add_argument("--file")
    args = parser.parse_args()

    created_ids: list[str] = []
    cleanup_failed = False

    try:
        status, health = http_json("GET", f"{args.base_url}/api/health")
        print(f"[PASS] health {status}: {health}")

        mock_video_url = f"/uploads/mock-smoke-{uuid.uuid4().hex}.mp4"
        status, created = http_json(
            "POST",
            f"{args.base_url}/api/breakdowns",
            body=json.dumps({"video_url": mock_video_url, "provider": "mock"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        created_ids.append(created["id"])
        print(f"[PASS] mock url breakdown {status}: {created['id']} {created['classification']['hook_type']}")

        if args.file:
            file_path = Path(args.file).resolve()
            body, boundary = multipart_body("file", file_path)
            upload_status, uploaded = http_json(
                "POST",
                f"{args.base_url}/api/breakdowns/upload?provider=mock",
                body=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
            created_ids.append(uploaded["id"])
            print(f"[PASS] upload breakdown {upload_status}: {uploaded['id']} {uploaded['classification']['hook_type']}")

        get_status, _ = http_json("GET", f"{args.base_url}/api/breakdowns/{created['id']}")
        print(f"[PASS] get breakdown {get_status}")

        export_status, content_type, markdown = http_text(
            "GET",
            f"{args.base_url}/api/breakdowns/{created['id']}/export/markdown",
        )
        if "text/markdown" not in content_type or "# 视频拆解报告" not in markdown:
            raise RuntimeError("Markdown export response did not match expected report format")
        print(f"[PASS] markdown export {export_status}: {len(markdown)} bytes")
    finally:
        for breakdown_id in reversed(created_ids):
            try:
                cleanup_status, _ = http_json("DELETE", f"{args.base_url}/api/breakdowns/{breakdown_id}")
                print(f"[PASS] cleanup breakdown {cleanup_status}: {breakdown_id}")
            except RuntimeError as exc:
                cleanup_failed = True
                print(f"[FAIL] cleanup breakdown {breakdown_id}: {exc}")

    if cleanup_failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
