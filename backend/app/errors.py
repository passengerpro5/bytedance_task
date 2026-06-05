from __future__ import annotations

from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


def bad_request(code: str, message: str) -> HTTPException:
    return api_error(400, code, message)


def not_found(code: str, message: str) -> HTTPException:
    return api_error(404, code, message)


def conflict(code: str, message: str) -> HTTPException:
    return api_error(409, code, message)


def unprocessable(code: str, message: str) -> HTTPException:
    return api_error(422, code, message)
