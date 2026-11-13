"""Account authentication, revocable opaque sessions, and shared rate limits.

Passwords use Argon2 via pwdlib. Only SHA-256 digests of random bearer tokens
are persisted. Every application has its own schema and user namespace.
"""

import hashlib
import secrets
import time
import uuid
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from pwdlib import PasswordHash
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

SCHEMA = """
CREATE TABLE IF NOT EXISTS beta_users (id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS beta_sessions (digest TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES beta_users(id), expires DOUBLE PRECISION NOT NULL, label TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS beta_sessions_owner ON beta_sessions(owner);
CREATE TABLE IF NOT EXISTS beta_limits (key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires DOUBLE PRECISION NOT NULL)
"""
passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash("not-a-real-account-password")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class Credentials(BaseModel):
    username: str = Field(pattern=r"^[a-zA-Z0-9_-]{3,40}$")
    password: str = Field(min_length=12, max_length=128)


class KeyRequest(BaseModel):
    label: str = Field(min_length=1, max_length=60)


class Accounts:
    def __init__(self, engine, slug):
        self.engine = engine
        self.slug = slug
        self.cookie = slug.replace("-", "_") + "_session"
        self.demo_username = "demo-" + slug.removeprefix("qq-")
        self.demo_password = slug.removeprefix("qq-").title() + "Beta!2026"
        self.router = APIRouter(prefix="/api/auth", tags=["Accounts"])
        self._routes()

    def initialize(self):
        with self.engine.begin() as db:
            for statement in SCHEMA.split(";"):
                if statement.strip():
                    db.execute(text(statement))
            exists = db.execute(
                text("SELECT id FROM beta_users WHERE username=:name"),
                {"name": self.demo_username},
            ).first()
            if not exists:
                db.execute(
                    text(
                        "INSERT INTO beta_users VALUES(:id,:name,:password,:created) ON CONFLICT(username) DO NOTHING"
                    ),
                    {
                        "id": "demo",
                        "name": self.demo_username,
                        "password": passwords.hash(self.demo_password),
                        "created": time.time(),
                    },
                )

    def limit(self, scope, maximum=120):
        now = time.time()
        bucket = int(now // 60)
        key = digest(scope) + ":" + str(bucket)
        with self.engine.begin() as db:
            db.execute(text("DELETE FROM beta_limits WHERE expires<:now"), {"now": now})
            row = db.execute(
                text(
                    "INSERT INTO beta_limits VALUES(:key,1,:expires) ON CONFLICT(key) DO UPDATE SET count=beta_limits.count+1 WHERE beta_limits.count<:maximum RETURNING count"
                ),
                {"key": key, "expires": now + 120, "maximum": maximum},
            ).first()
        if not row:
            raise HTTPException(
                429,
                "Too many requests. Try again in one minute.",
                headers={"Retry-After": "60"},
            )

    def origin(self, request):
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).netloc != request.headers.get("host"):
            raise HTTPException(403, "Cross-origin request rejected")

    def token(self, request):
        authorization = request.headers.get("authorization", "")
        if authorization.startswith("Bearer "):
            return authorization[7:]
        return request.cookies.get(self.cookie, "")

    def user(self, request: Request):
        raw = self.token(request)
        if not raw:
            raise HTTPException(401, "Sign in to continue")
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            self.origin(request)
            if not request.headers.get("authorization") and not request.headers.get(
                "origin"
            ):
                raise HTTPException(403, "Origin header required for cookie mutations")
        with self.engine.connect() as db:
            row = (
                db.execute(
                    text(
                        "SELECT u.id,u.username FROM beta_sessions s JOIN beta_users u ON u.id=s.owner WHERE s.digest=:digest AND s.expires>:now"
                    ),
                    {"digest": digest(raw), "now": time.time()},
                )
                .mappings()
                .first()
            )
        if not row:
            raise HTTPException(401, "Session expired or revoked")
        self.limit("account:" + row["id"])
        return dict(row)

    def issue(self, owner, label, seconds):
        raw = secrets.token_urlsafe(32)
        with self.engine.begin() as db:
            db.execute(
                text("DELETE FROM beta_sessions WHERE expires<:now"),
                {"now": time.time()},
            )
            db.execute(
                text(
                    "INSERT INTO beta_sessions VALUES(:digest,:owner,:expires,:label)"
                ),
                {
                    "digest": digest(raw),
                    "owner": owner,
                    "expires": time.time() + seconds,
                    "label": label,
                },
            )
        return raw

    def _routes(self):
        router = self.router

        @router.get("/demo")
        def demo_credentials():
            return {
                "username": self.demo_username,
                "password": self.demo_password,
                "notice": "Shared public account. Use synthetic data only, or create your own account.",
            }

        @router.post("/register", status_code=201)
        def register(body: Credentials, request: Request):
            self.origin(request)
            self.limit(
                "register:"
                + request.headers.get(
                    "x-forwarded-for",
                    request.client.host if request.client else "unknown",
                ),
                5,
            )
            username = body.username.lower()
            if username.startswith("demo-"):
                raise HTTPException(400, "The demo prefix is reserved")
            identifier = str(uuid.uuid4())
            hashed = passwords.hash(body.password)
            try:
                with self.engine.begin() as db:
                    db.execute(
                        text(
                            "INSERT INTO beta_users VALUES(:id,:username,:password,:created)"
                        ),
                        {
                            "id": identifier,
                            "username": username,
                            "password": hashed,
                            "created": time.time(),
                        },
                    )
            except IntegrityError:
                raise HTTPException(409, "Username is already taken")
            return {"id": identifier, "username": username}

        @router.post("/login")
        def login(body: Credentials, request: Request, response: Response):
            self.origin(request)
            self.limit(
                "login:"
                + request.headers.get(
                    "x-forwarded-for",
                    request.client.host if request.client else "unknown",
                ),
                15,
            )
            with self.engine.connect() as db:
                row = (
                    db.execute(
                        text("SELECT * FROM beta_users WHERE username=:name"),
                        {"name": body.username.lower()},
                    )
                    .mappings()
                    .first()
                )
            valid = passwords.verify(
                body.password, row["password_hash"] if row else DUMMY_HASH
            )
            if not row or not valid:
                raise HTTPException(401, "Invalid username or password")
            token = self.issue(row["id"], "Browser session", 7 * 86400)
            response.set_cookie(
                self.cookie,
                token,
                max_age=7 * 86400,
                httponly=True,
                secure=request.url.scheme == "https",
                samesite="lax",
                path="/",
            )
            return {"id": row["id"], "username": row["username"]}

        @router.get("/me")
        def me(user=Depends(self.user)):
            return user

        @router.post("/logout")
        def logout(request: Request, response: Response, user=Depends(self.user)):
            with self.engine.begin() as db:
                db.execute(
                    text(
                        "DELETE FROM beta_sessions WHERE digest=:digest AND owner=:owner"
                    ),
                    {"digest": digest(self.token(request)), "owner": user["id"]},
                )
            response.delete_cookie(self.cookie, path="/")
            return {"ok": True}

        @router.post("/keys", status_code=201)
        def create_key(body: KeyRequest, user=Depends(self.user)):
            self.limit("key-create:" + user["id"], 5)
            token = self.issue(user["id"], "API: " + body.label, 30 * 86400)
            return {
                "token": token,
                "expires_in_days": 30,
                "notice": "Copy now. This token grants access to your account API.",
            }

        @router.get("/keys")
        def keys(user=Depends(self.user)):
            with self.engine.connect() as db:
                return [
                    dict(r)
                    for r in db.execute(
                        text(
                            "SELECT digest,label,expires FROM beta_sessions WHERE owner=:owner AND expires>:now AND label!='Browser session' ORDER BY expires DESC LIMIT 100"
                        ),
                        {"owner": user["id"], "now": time.time()},
                    ).mappings()
                ]

        @router.delete("/keys/{identifier}")
        def revoke(identifier: str, user=Depends(self.user)):
            with self.engine.begin() as db:
                db.execute(
                    text("DELETE FROM beta_sessions WHERE digest=:id AND owner=:owner"),
                    {"id": identifier, "owner": user["id"]},
                )
            return {"ok": True}
