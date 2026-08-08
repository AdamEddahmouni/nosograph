"""Authentication endpoints for local development and trusted proxy deployments."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.responses import Response

from med_research.web.services.auth import (
    _mode,
    auth_status,
    authenticate_local_user,
    clear_session_cookie,
    login_response,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1000)


@router.get("/me")
def current_principal(request: Request) -> dict[str, Any]:
    return auth_status(request)


@router.post("/login")
def login(payload: LoginRequest) -> Response:
    if _mode() != "local":
        raise HTTPException(
            status_code=409,
            detail="Interactive local login is disabled; use the configured identity proxy",
        )
    researcher_id = authenticate_local_user(payload.username, payload.password)
    if researcher_id is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return login_response(researcher_id)


@router.post("/logout")
def logout() -> Response:
    response = Response(content='{"authenticated":false}', media_type="application/json")
    clear_session_cookie(response)
    return response
