"""Tests for the JobRadar Authentication & Session API."""

from datetime import datetime, timezone, timedelta
import os
import unittest
from fastapi import HTTPException

from job_market.api import create_app
from job_market.auth_api import (
    RegisterRequest,
    LoginRequest,
    ProfileUpdateRequest,
    register,
    login,
    get_current_user,
    update_profile,
    logout,
    get_auth_db,
    init_auth_db,
    clear_rate_limit,
)


class TestAuthAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_auth_db()
        # Reset demo user to baseline
        with get_auth_db() as conn:
            conn.execute("UPDATE users SET target_role = 'Data Scientist', current_skills = '[\"Python\", \"SQL\", \"Pandas\", \"NumPy\", \"Git\", \"Excel\"]' WHERE username = 'aarav_ds'")
            conn.commit()
        cls.app = create_app()

    def setUp(self):
        clear_rate_limit("127.0.0.1")

    def tearDown(self):
        clear_rate_limit("127.0.0.1")
        # Reset demo user state after tests
        with get_auth_db() as conn:
            conn.execute("UPDATE users SET target_role = 'Data Scientist', current_skills = '[\"Python\", \"SQL\", \"Pandas\", \"NumPy\", \"Git\", \"Excel\"]' WHERE username = 'aarav_ds'")
            conn.commit()

    def test_01_demo_login_success(self):
        """Test successful login with pre-seeded demo user."""
        res = login(LoginRequest(username="aarav_ds", password="password123"))
        self.assertTrue(res["success"])
        self.assertIn("token", res)
        self.assertEqual(res["user"]["username"], "aarav_ds")
        self.assertEqual(res["user"]["targetRole"], "Data Scientist")
        self.assertTrue(res["user"]["hasCompletedOnboarding"])

    def test_02_login_invalid_password(self):
        """Test login fails with incorrect password."""
        with self.assertRaises(HTTPException) as ctx:
            login(LoginRequest(username="aarav_ds", password="wrongpassword!"))
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Invalid username or password", ctx.exception.detail)

    def test_03_login_nonexistent_user(self):
        """Test login fails for unknown username."""
        with self.assertRaises(HTTPException) as ctx:
            login(LoginRequest(username="nonexistent_user_xyz", password="password123"))
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Invalid username or password", ctx.exception.detail)

    def test_04_register_success(self):
        """Test registering a new account successfully."""
        unique_handle = f"tester_{int(datetime.now().timestamp() * 1000)}"
        unique_email = f"{unique_handle}@example.com"
        res = register(
            RegisterRequest(
                name="QA Tester",
                username=unique_handle,
                email=unique_email,
                password="secure_password_2026",
            )
        )
        self.assertTrue(res["success"])
        self.assertIn("token", res)
        self.assertEqual(res["user"]["username"], unique_handle)
        self.assertFalse(res["user"]["hasCompletedOnboarding"])

        # Verify we can immediately login with this new account
        login_res = login(LoginRequest(username=unique_handle, password="secure_password_2026"))
        self.assertTrue(login_res["success"])
        self.assertEqual(login_res["user"]["id"], res["user"]["id"])

    def test_05_register_duplicate_username(self):
        """Test registration rejection when username already exists."""
        with self.assertRaises(HTTPException) as ctx:
            register(
                RegisterRequest(
                    name="Duplicate Aarav",
                    username="aarav_ds",
                    email="different_email@example.com",
                    password="password123",
                )
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("already taken", ctx.exception.detail)

    def test_06_register_duplicate_email(self):
        """Test registration rejection when email already exists."""
        with self.assertRaises(HTTPException) as ctx:
            register(
                RegisterRequest(
                    name="Duplicate Email",
                    username="brand_new_handle",
                    email="aarav@example.com",
                    password="password123",
                )
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("already registered", ctx.exception.detail)

    def test_07_register_invalid_email(self):
        """Test registration rejects invalid email format."""
        with self.assertRaises(HTTPException) as ctx:
            register(
                RegisterRequest(
                    name="Bad Email",
                    username="bad_email_user",
                    email="not-an-email",
                    password="password123",
                )
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Invalid email format", ctx.exception.detail)

    def test_08_get_me_valid_token(self):
        """Test get_current_user returns authenticated user profile."""
        login_res = login(LoginRequest(username="aarav_ds", password="password123"))
        token = login_res["token"]

        me_res = get_current_user(authorization=f"Bearer {token}")
        self.assertTrue(me_res["success"])
        self.assertEqual(me_res["user"]["username"], "aarav_ds")

    def test_09_get_me_unauthorized(self):
        """Test get_current_user fails when unauthenticated or token is bogus."""
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(authorization=None)
        self.assertEqual(ctx.exception.status_code, 401)

        with self.assertRaises(HTTPException) as ctx:
            get_current_user(authorization="Bearer bogus_fake_token_123")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_10_update_profile(self):
        """Test update_profile updates user attributes."""
        login_res = login(LoginRequest(username="aarav_ds", password="password123"))
        token = login_res["token"]

        update_res = update_profile(
            updates=ProfileUpdateRequest(
                targetRole="Machine Learning Engineer",
                currentSkills=["Python", "PyTorch", "Docker"],
            ),
            authorization=f"Bearer {token}",
        )
        self.assertTrue(update_res["success"])
        self.assertEqual(update_res["user"]["targetRole"], "Machine Learning Engineer")
        self.assertIn("PyTorch", update_res["user"]["currentSkills"])

    def test_11_logout_revokes_token(self):
        """Test logout invalidates session token."""
        login_res = login(LoginRequest(username="aarav_ds", password="password123"))
        token = login_res["token"]

        # Logout
        logout_res = logout(authorization=f"Bearer {token}")
        self.assertTrue(logout_res["success"])

        # Token should now be invalid
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(authorization=f"Bearer {token}")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_12_expired_session(self):
        """Test expired session token is rejected with 401."""
        login_res = login(LoginRequest(username="aarav_ds", password="password123"))
        user_id = login_res["user"]["id"]

        # Inject an expired session manually into the auth database
        expired_token = "expired_token_for_testing"
        past_date = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        with get_auth_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (expired_token, user_id, past_date, past_date),
            )
            conn.commit()

        with self.assertRaises(HTTPException) as ctx:
            get_current_user(authorization=f"Bearer {expired_token}")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("expired", ctx.exception.detail.lower())

    def test_13_password_complexity_validation(self):
        """Test registration rejects weak passwords (under 8 chars or missing digits)."""
        # Under 8 chars
        with self.assertRaises(Exception):
            register(
                RegisterRequest(
                    name="Weak Pwd",
                    username="weak_pwd_user",
                    email="weak@example.com",
                    password="abc1",
                )
            )

        # 8 chars but no digits
        with self.assertRaises(HTTPException) as ctx:
            register(
                RegisterRequest(
                    name="No Digits",
                    username="nodigits_user",
                    email="nodigits@example.com",
                    password="abcdefghijkl",
                )
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("at least 8 characters long and contain both letters and digits", ctx.exception.detail)

    def test_14_rate_limiting_brute_force(self):
        """Test rate limiting locks out client after 5 consecutive failed login attempts."""
        clear_rate_limit("127.0.0.1")
        # Fail 4 times (under limit)
        for _ in range(4):
            with self.assertRaises(HTTPException) as ctx:
                login(LoginRequest(username="aarav_ds", password="wrong_pass_test"))
            self.assertEqual(ctx.exception.status_code, 401)

        # 5th failure
        with self.assertRaises(HTTPException) as ctx:
            login(LoginRequest(username="aarav_ds", password="wrong_pass_test"))
        self.assertEqual(ctx.exception.status_code, 401)

        # 6th attempt should be blocked with 429
        with self.assertRaises(HTTPException) as ctx:
            login(LoginRequest(username="aarav_ds", password="password123"))
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("temporarily locked", ctx.exception.detail)

    def test_15_production_demo_account_disabled(self):
        """Test default demo account login is blocked in production."""
        old_env = os.environ.get("JOBRADAR_ENV")
        try:
            os.environ["JOBRADAR_ENV"] = "production"
            with self.assertRaises(HTTPException) as ctx:
                login(LoginRequest(username="aarav_ds", password="password123"))
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertIn("disabled in production", ctx.exception.detail)
        finally:
            if old_env is not None:
                os.environ["JOBRADAR_ENV"] = old_env
            else:
                os.environ.pop("JOBRADAR_ENV", None)


if __name__ == "__main__":
    unittest.main()
