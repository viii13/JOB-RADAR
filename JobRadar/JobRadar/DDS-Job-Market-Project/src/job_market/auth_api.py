"""Authentication and user session API for JobRadar.

Provides persistent user accounts, PBKDF2 password hashing, session tokens,
and profile synchronization using a dedicated SQLite database (data/auth_users.db),
strictly isolated from the primary job intelligence database.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from typing import Any, Generator

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUTH_DB_PATH = PROJECT_ROOT / "data" / "auth_users.db"
SESSION_EXPIRATION_HOURS = 24
PBKDF2_ROUNDS = int(os.environ.get("PBKDF2_ROUNDS", "100000"))

# In-memory sliding-window rate limiting for brute-force protection
_failed_login_attempts: dict[str, list[float]] = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 60.0


def check_rate_limit(client_ip: str) -> None:
    """Check if the client IP has exceeded the maximum allowed failed attempts."""
    now = time.time()
    attempts = _failed_login_attempts.get(client_ip, [])
    # Retain attempts within the sliding window
    valid_attempts = [t for t in attempts if now - t < LOCKOUT_WINDOW_SECONDS]
    _failed_login_attempts[client_ip] = valid_attempts
    if len(valid_attempts) >= MAX_FAILED_ATTEMPTS:
        remaining = int(LOCKOUT_WINDOW_SECONDS - (now - valid_attempts[0]))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Account temporarily locked for {max(1, remaining)} seconds.",
        )


def record_failed_attempt(client_ip: str) -> None:
    """Record a failed login attempt for the client IP."""
    now = time.time()
    attempts = _failed_login_attempts.get(client_ip, [])
    attempts.append(now)
    _failed_login_attempts[client_ip] = attempts


def clear_rate_limit(client_ip: str) -> None:
    """Reset rate limiting for a client IP upon successful login."""
    _failed_login_attempts.pop(client_ip, None)


def is_demo_account_allowed() -> bool:
    """Determine whether the default demo account ('aarav_ds') is permitted.

    In production environments (JOBRADAR_ENV=production or ALLOW_DEMO_ACCOUNT=false),
    the default demo account cannot be seeded or logged into.
    """
    env = os.environ.get("JOBRADAR_ENV", "development").strip().lower()
    demo_flag = os.environ.get("ALLOW_DEMO_ACCOUNT", "").strip().lower()

    if demo_flag in ("false", "0", "no", "disabled"):
        return False
    if env in ("production", "prod") and demo_flag not in ("true", "1", "yes"):
        return False
    return True


@contextmanager
def get_auth_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for the isolated auth database with guaranteed closure."""
    AUTH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(AUTH_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_auth_db() -> None:
    """Initialize auth tables and conditionally seed demo user if permitted."""
    with get_auth_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                has_completed_onboarding INTEGER DEFAULT 0,
                education TEXT,
                degree TEXT,
                current_year_or_exp TEXT,
                experience_level TEXT,
                target_role TEXT DEFAULT 'Data Scientist',
                career_goal TEXT,
                preferred_location TEXT DEFAULT 'Bangalore, KA',
                preferred_work_type TEXT DEFAULT 'Hybrid',
                current_skills TEXT DEFAULT '[]',
                target_skills TEXT DEFAULT '[]',
                industry_preferences TEXT DEFAULT '[]',
                saved_job_ids TEXT DEFAULT '[]',
                applied_job_ids TEXT DEFAULT '[]',
                completed_roadmap_item_ids TEXT DEFAULT '[]',
                in_progress_roadmap_item_ids TEXT DEFAULT '[]',
                completed_resource_ids TEXT DEFAULT '[]'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)")
        conn.commit()

        # Conditionally seed demo user only when permitted
        if is_demo_account_allowed():
            row = conn.execute("SELECT id FROM users WHERE username = 'aarav_ds'").fetchone()
            if not row:
                salt = secrets.token_hex(16)
                pwd_hash = hash_password("password123", salt)
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    """
                    INSERT INTO users (
                        id, username, email, name, password_hash, salt, created_at,
                        has_completed_onboarding, education, degree, current_year_or_exp,
                        experience_level, target_role, career_goal, preferred_location,
                        preferred_work_type, current_skills, target_skills,
                        industry_preferences, saved_job_ids, applied_job_ids,
                        completed_roadmap_item_ids, in_progress_roadmap_item_ids,
                        completed_resource_ids
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "usr-demo-01",
                        "aarav_ds",
                        "aarav@example.com",
                        "Aarav Sharma",
                        pwd_hash,
                        salt,
                        now,
                        1,
                        "B.Tech in Computer Science & AI",
                        "Computer Science",
                        "Final Year (2025)",
                        "Fresher / Entry (0-1 yrs)",
                        "Data Scientist",
                        "Land a Data Scientist or Associate ML role at a product startup",
                        "Bangalore, KA",
                        "Hybrid",
                        json.dumps(["Python", "SQL", "Pandas", "NumPy", "Git", "Excel"]),
                        json.dumps(["Machine Learning", "Scikit-learn", "Statistics", "NLP", "AWS"]),
                        json.dumps(["Fintech", "E-commerce", "AI/SaaS"]),
                        json.dumps(["job-1", "job-3", "job-8"]),
                        json.dumps(["job-2"]),
                        json.dumps(["ds-1-1", "ds-1-2", "ds-2-1"]),
                        json.dumps(["ds-1-3", "ds-2-2", "ds-4-1"]),
                        json.dumps([]),
                    ),
                )
                conn.commit()
                logger.info("Default demo account 'aarav_ds' initialized for local development.")


def hash_password(password: str, salt: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256."""
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS)
    return dk.hex()


def user_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert SQLite Row to JSON-serializable user profile dictionary."""
    def parse_json(val: Any) -> list:
        if not val:
            return []
        try:
            return json.loads(val)
        except Exception:
            return []

    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "name": row["name"],
        "hasCompletedOnboarding": bool(row["has_completed_onboarding"]),
        "education": row["education"] or "",
        "degree": row["degree"] or "",
        "currentYearOrExp": row["current_year_or_exp"] or "",
        "experienceLevel": row["experience_level"] or "",
        "targetRole": row["target_role"] or "Data Scientist",
        "careerGoal": row["career_goal"] or "",
        "preferredLocation": row["preferred_location"] or "Bangalore, KA",
        "preferredWorkType": row["preferred_work_type"] or "Hybrid",
        "currentSkills": parse_json(row["current_skills"]),
        "targetSkills": parse_json(row["target_skills"]),
        "industryPreferences": parse_json(row["industry_preferences"]),
        "savedJobIds": parse_json(row["saved_job_ids"]),
        "appliedJobIds": parse_json(row["applied_job_ids"]),
        "completedRoadmapItemIds": parse_json(row["completed_roadmap_item_ids"]),
        "inProgressRoadmapItemIds": parse_json(row["in_progress_roadmap_item_ids"]),
        "completedResourceIds": parse_json(row["completed_resource_ids"]),
    }


def create_session(user_id: str) -> tuple[str, str]:
    """Generate and store a new session token, returning (token, expires_at)."""
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=SESSION_EXPIRATION_HOURS)
    with get_auth_db() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now.isoformat(), expires.isoformat()),
        )
        conn.commit()
    return token, expires.isoformat()


def validate_token(authorization: str | None) -> dict[str, Any]:
    """Validate Bearer token from header; returns user dictionary or raises HTTPException."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization scheme. Use 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = parts[1]

    with get_auth_db() as conn:
        session = conn.execute(
            "SELECT token, user_id, expires_at FROM sessions WHERE token = ?", (token,)
        ).fetchone()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        expires_at = datetime.fromisoformat(session["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has expired. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account associated with session no longer exists",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user_row_to_dict(user)


# Request & Response Schemas
class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Full name of user")
    username: str = Field(..., min_length=3, max_length=50, description="Unique username handle")
    email: str = Field(..., description="Valid email address")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters with letters and numbers)")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Username handle")
    password: str = Field(..., min_length=1, description="Password")


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    education: str | None = None
    degree: str | None = None
    currentYearOrExp: str | None = None
    experienceLevel: str | None = None
    targetRole: str | None = None
    careerGoal: str | None = None
    preferredLocation: str | None = None
    preferredWorkType: str | None = None
    hasCompletedOnboarding: bool | None = None
    currentSkills: list[str] | None = None
    targetSkills: list[str] | None = None
    industryPreferences: list[str] | None = None
    savedJobIds: list[str] | None = None
    appliedJobIds: list[str] | None = None
    completedRoadmapItemIds: list[str] | None = None
    inProgressRoadmapItemIds: list[str] | None = None
    completedResourceIds: list[str] | None = None


# Routes
@auth_router.post("/register", status_code=status.HTTP_201_CREATED, summary="Register a new user account")
def register(req: RegisterRequest) -> dict[str, Any]:
    username_norm = req.username.strip().lower()
    email_norm = req.email.strip().lower()

    if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email_norm):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email format")

    if len(req.password) < 8 or not any(c.isdigit() for c in req.password) or not any(c.isalpha() for c in req.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long and contain both letters and digits.",
        )

    with get_auth_db() as conn:
        existing_user = conn.execute(
            "SELECT id FROM users WHERE LOWER(username) = ?", (username_norm,)
        ).fetchone()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Username '{req.username}' is already taken",
            )

        existing_email = conn.execute(
            "SELECT id FROM users WHERE LOWER(email) = ?", (email_norm,)
        ).fetchone()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{req.email}' is already registered",
            )

        user_id = f"usr-{secrets.token_hex(6)}"
        salt = secrets.token_hex(16)
        pwd_hash = hash_password(req.password, salt)
        now = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """
            INSERT INTO users (
                id, username, email, name, password_hash, salt, created_at,
                has_completed_onboarding, target_role, preferred_location, preferred_work_type,
                current_skills, target_skills, industry_preferences, saved_job_ids,
                applied_job_ids, completed_roadmap_item_ids, in_progress_roadmap_item_ids,
                completed_resource_ids
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                req.username.strip(),
                email_norm,
                req.name.strip(),
                pwd_hash,
                salt,
                now,
                0,  # Needs onboarding
                "Data Scientist",
                "Bangalore, KA",
                "Hybrid",
                json.dumps([]),
                json.dumps([]),
                json.dumps([]),
                json.dumps([]),
                json.dumps([]),
                json.dumps([]),
                json.dumps([]),
                json.dumps([]),
            ),
        )
        conn.commit()

        user_row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        token, expires_at = create_session(user_id)

    return {
        "success": True,
        "token": token,
        "expires_at": expires_at,
        "user": user_row_to_dict(user_row),
    }


@auth_router.post("/login", summary="Authenticate with username and password")
def login(req: LoginRequest, request: Request = None) -> dict[str, Any]:
    client_ip = request.client.host if request and request.client else "127.0.0.1"
    check_rate_limit(client_ip)

    username_norm = req.username.strip().lower()

    # Enforce demo account security in production
    if username_norm == "aarav_ds" and not is_demo_account_allowed():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Default demo account is disabled in production environments.",
        )

    with get_auth_db() as conn:
        user_row = conn.execute(
            "SELECT * FROM users WHERE LOWER(username) = ?", (username_norm,)
        ).fetchone()

        if not user_row:
            record_failed_attempt(client_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        expected_hash = hash_password(req.password, user_row["salt"])
        if not secrets.compare_digest(expected_hash, user_row["password_hash"]):
            record_failed_attempt(client_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        clear_rate_limit(client_ip)
        token, expires_at = create_session(user_row["id"])

    return {
        "success": True,
        "token": token,
        "expires_at": expires_at,
        "user": user_row_to_dict(user_row),
    }


@auth_router.get("/me", summary="Fetch active authenticated user profile")
def get_current_user(authorization: str | None = Header(None)) -> dict[str, Any]:
    user = validate_token(authorization)
    return {"success": True, "user": user}


@auth_router.put("/profile", summary="Update authenticated user profile attributes")
def update_profile(updates: ProfileUpdateRequest, authorization: str | None = Header(None)) -> dict[str, Any]:
    current_user = validate_token(authorization)
    user_id = current_user["id"]

    field_map = {
        "name": ("name", lambda v: v),
        "education": ("education", lambda v: v),
        "degree": ("degree", lambda v: v),
        "currentYearOrExp": ("current_year_or_exp", lambda v: v),
        "experienceLevel": ("experience_level", lambda v: v),
        "targetRole": ("target_role", lambda v: v),
        "careerGoal": ("career_goal", lambda v: v),
        "preferredLocation": ("preferred_location", lambda v: v),
        "preferredWorkType": ("preferred_work_type", lambda v: v),
        "hasCompletedOnboarding": ("has_completed_onboarding", lambda v: 1 if v else 0),
        "currentSkills": ("current_skills", lambda v: json.dumps(v)),
        "targetSkills": ("target_skills", lambda v: json.dumps(v)),
        "industryPreferences": ("industry_preferences", lambda v: json.dumps(v)),
        "savedJobIds": ("saved_job_ids", lambda v: json.dumps(v)),
        "appliedJobIds": ("applied_job_ids", lambda v: json.dumps(v)),
        "completedRoadmapItemIds": ("completed_roadmap_item_ids", lambda v: json.dumps(v)),
        "inProgressRoadmapItemIds": ("in_progress_roadmap_item_ids", lambda v: json.dumps(v)),
        "completedResourceIds": ("completed_resource_ids", lambda v: json.dumps(v)),
    }

    set_clauses = []
    params = []
    update_dict = updates.model_dump(exclude_unset=True)

    for key, val in update_dict.items():
        if key in field_map:
            col, transform = field_map[key]
            set_clauses.append(f"{col} = ?")
            params.append(transform(val))

    if set_clauses:
        params.append(user_id)
        with get_auth_db() as conn:
            conn.execute(f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?", params)
            conn.commit()
            updated_row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return {"success": True, "user": user_row_to_dict(updated_row)}

    return {"success": True, "user": current_user}


@auth_router.post("/logout", summary="Revoke active user session")
def logout(authorization: str | None = Header(None)) -> dict[str, Any]:
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
            with get_auth_db() as conn:
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()
    return {"success": True, "message": "Successfully logged out"}


# Initialize auth tables and seed demo user on module load
init_auth_db()
