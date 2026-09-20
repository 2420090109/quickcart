"""Auth pages — HTML routes for login / signup / logout."""
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.session import clear_session_cookies, set_session_cookies
from app.core.templating import templates
from app.db.session import get_db
from app.schemas.user import UserCreate
from app.services.auth_service import AuthError, login_user, register_user
logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth-pages"])
def _ctx(request: Request, **extra):
    return {
        "request": request,
        "current_user": getattr(request.state, "current_user", None),
        **extra,
    }
def _error(request: Request, message: str) -> HTMLResponse:
    """Return an HTML fragment that HTMX swaps into the error slot."""
    return templates.TemplateResponse(
        "auth/_error.html", _ctx(request, message=message), status_code=200
    )
@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request) -> Response:
    if getattr(request.state, "current_user", None):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("auth/login.html", _ctx(request))
@router.post("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_submit(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    phone: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
) -> Response:
    phone = (phone or "").strip()
    password = password or ""
    if not phone or not password:
        return _error(request, "Please enter both phone and password.")
    try:
        user, tokens = await login_user(db, phone, password)
    except AuthError as e:
        return _error(request, e.message)
    except Exception:
        logger.exception("Login crashed")
        return _error(request, "Something went wrong. Please try again.")
    response = Response(status_code=204)
    response.headers["HX-Redirect"] = "/"
    set_session_cookies(response, access=tokens.access_token, refresh=tokens.refresh_token)
    return response
@router.get("/signup", response_class=HTMLResponse, include_in_schema=False)
async def signup_page(request: Request) -> Response:
    if getattr(request.state, "current_user", None):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("auth/signup.html", _ctx(request))
@router.post("/signup", response_class=HTMLResponse, include_in_schema=False)
async def signup_submit(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    full_name: Annotated[str, Form()] = "",
    phone: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
    email: Annotated[str | None, Form()] = None,
) -> Response:
    full_name = (full_name or "").strip()
    phone = (phone or "").strip()
    password = password or ""
    email = (email or "").strip() or None
    # --- Friendly manual validation (so we always render our styled error) ---
    if not full_name or len(full_name) < 2:
        return _error(request, "Please enter your full name.")
    if not phone or not phone.isdigit() or not (10 <= len(phone) <= 15):
        return _error(request, "Phone must be 10–15 digits.")
    if len(password) < 8:
        return _error(request, "Password must be at least 8 characters.")
    try:
        data = UserCreate(
            phone=phone,
            full_name=full_name,
            password=password,
            email=email,
        )
        user, tokens = await register_user(db, data)
    except AuthError as e:
        return _error(request, e.message)
    except Exception as e:
        logger.exception("Signup failed")
        return _error(request, f"Could not create account: {e}")
    response = Response(status_code=204)
    response.headers["HX-Redirect"] = "/"
    set_session_cookies(response, access=tokens.access_token, refresh=tokens.refresh_token)
    return response
@router.post("/logout", include_in_schema=False)
async def logout() -> Response:
    response = RedirectResponse(url="/", status_code=303)
    clear_session_cookies(response)
    return response