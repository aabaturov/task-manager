from fastapi import HTTPException, Request, status

from .config import settings

SESSION_KEY = "authed"


def check_credentials(login: str, password: str) -> bool:
    return login == settings.web_login and password == settings.web_password


def login_session(request: Request) -> None:
    request.session[SESSION_KEY] = True


def logout_session(request: Request) -> None:
    request.session.pop(SESSION_KEY, None)


def require_auth(request: Request) -> None:
    if not request.session.get(SESSION_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
