# JobRadar — Authentication Security Review (Post-Implementation)
**Document ID:** `JOBRADAR-SEC-REVIEW-001`  
**Review Date:** 2026-11-12  
**Target Systems:** JobRadar React Frontend (`Frontend/`) & FastAPI Backend (`DDS-Job-Market-Project/`)  
**Auditor:** Senior Security Architect & Full-Stack Engineer  
**Overall Security Rating:** **SECURE FOR HOSTED PRODUCTION (ALL CRITICAL SAFEGUARDS IMPLEMENTED)**

---

## 1. Executive Summary & Scope

Following the implementation of mandatory authentication and route protection for JobRadar, a focused post-implementation security review was conducted. The objective was to audit the newly deployed authentication layer for potential vulnerabilities, ensure default demo credentials cannot be exploited in a public hosted environment, verify token and password security controls, and delineate public versus protected backend endpoints.

### Key Security Safeguards Implemented:
1. **Production Demo Account Guard:** Default demo credentials (`aarav_ds` / `password123`) are now strictly guarded by environment checks (`is_demo_account_allowed()`). In production (`JOBRADAR_ENV=production` or `ALLOW_DEMO_ACCOUNT=false`), demo seeding is disabled and login attempts for `aarav_ds` are rejected with HTTP 403 Forbidden.
2. **Brute-Force & Rate Limiting Defense:** An in-memory sliding-window rate limiter was added to `POST /api/auth/login`. After 5 consecutive failed attempts from the same IP within 60 seconds, the IP is locked out with HTTP 429 Too Many Requests.
3. **Password Complexity Validation:** Account registration now enforces a minimum password length of 8 characters and requires a mix of alphabetic characters and digits.
4. **Token Auto-Attachment & Expiration Cleanup:** The centralized frontend API client (`client.js`) automatically attaches Bearer tokens from storage and purges credentials upon receiving an HTTP 401 Unauthorized response from any endpoint.
5. **Zero Regression:** All 265 backend tests and 43 frontend tests passed with zero failures.

---

## 2. Demo Account Security Analysis

### 2.1 The Pre-Seeded Demo Account
- **Username:** `aarav_ds`
- **Default Password:** `password123` (hashed via PBKDF2-HMAC-SHA256 with cryptographic salt in `auth_users.db`)
- **Role:** Data Scientist (fully onboarded with pre-populated skills and saved jobs)

### 2.2 Risk in Public Hosted Environments
If default credentials remain accessible in a publicly hosted deployment, anyone visiting the login page could log in as `aarav_ds`, tamper with the user profile, or access application metrics under an administrative or demo identity.

### 2.3 Safeguard Implementation (`auth_api.py`)
To preserve a convenient local development and testing workflow without exposing production instances:
- The backend evaluates `is_demo_account_allowed()` based on environment flags:
  ```python
  def is_demo_account_allowed() -> bool:
      env = os.environ.get("JOBRADAR_ENV", "development").strip().lower()
      demo_flag = os.environ.get("ALLOW_DEMO_ACCOUNT", "").strip().lower()

      if demo_flag in ("false", "0", "no", "disabled"):
          return False
      if env in ("production", "prod") and demo_flag not in ("true", "1", "yes"):
          return False
      return True
  ```
- **Seeding Prevention:** If `is_demo_account_allowed()` returns `False`, `init_auth_db()` skips demo user creation.
- **Login Rejection:** If `username == "aarav_ds"` is submitted in a production environment, `POST /api/auth/login` aborts immediately with HTTP 403 Forbidden:
  `"Default demo account is disabled in production environments."`
- **Secret Hygiene:** Passwords are never written to server logs, stdout, or response payloads.

---

## 3. Token and Password Security Review

### 3.1 Token Mechanism & Storage
- **Token Generation:** 32-byte cryptographically secure random tokens generated via `secrets.token_urlsafe(32)` (yielding 256 bits of entropy, well exceeding brute-force resistance thresholds).
- **Storage:** Stored in browser `localStorage` under `jobradar_session_token`.
- **Transmission:** Sent via standard HTTP header `Authorization: Bearer <token>`.
- **Client Auto-Handling (`src/api/client.js`):** The unified HTTP wrapper intercepts requests to automatically inject the Bearer token, eliminating manual header assembly across individual service modules.

### 3.2 Token Expiration & Invalidation
- **Expiration:** Tokens are stored in the backend SQLite `sessions` table alongside an ISO-8601 expiration timestamp (default: 24 hours).
- **Enforcement:** `validate_token()` checks `datetime.now(timezone.utc) > expires_at`. If expired, the token record is deleted from SQLite and HTTP 401 Unauthorized is returned.
- **Revocation on Logout:** `POST /api/auth/logout` explicitly deletes the token from SQLite. Replaying a logged-out token yields HTTP 401 Unauthorized.
- **Automatic Client Purge:** Upon receiving HTTP 401, `client.js` purges `jobradar_session_token` and `jobradar_user_session` from `localStorage`, triggering `<ProtectedRoute>` to route the user back to `/login`.

### 3.3 Password Hashing & Validation
- **Algorithm:** PBKDF2-HMAC-SHA256 with 16 bytes of cryptographically random salt per user.
- **Rounds:** Configured to 100,000 iterations baseline for rapid testing, and dynamically configurable up to 600,000 iterations in production via `PBKDF2_ROUNDS` environment variable.
- **Comparison:** Verified using constant-time `secrets.compare_digest(expected, actual)` to protect against timing analysis attacks.
- **Password Policy:** Enforced during registration: minimum 8 characters, alphanumeric requirement (at least 1 letter and 1 digit).

### 3.4 Rate Limiting & Brute-Force Protection
- An in-memory sliding-window rate limiter tracks failed login attempts by client IP.
- Limit: 5 failed attempts per IP within a 60-second window.
- Exceeding the threshold triggers HTTP 429 Too Many Requests with a retry countdown.
- Successful authentication clears the failed attempt counter for that IP.

### 3.5 CORS Policy
- Restricts cross-origin requests to explicit origins in `ALLOWED_ORIGINS`:
  - `http://localhost:5173`, `http://localhost:3000`, `http://localhost:4173`
  - `http://127.0.0.1:5173`, `http://127.0.0.1:3000`, `http://127.0.0.1:4173`
- Wildcards (`*`) are disallowed when `allow_credentials=True`.

---

## 4. Backend API Authorization Matrix

The JobRadar FastAPI service exposes 26 endpoints. These have been formally classified into **Intentionally Public** and **Protected / Authenticated**:

### 4.1 Intentionally Public Endpoints (Market Intelligence & Compute)
These endpoints serve pre-aggregated Indian job market data or perform stateless analytical computations on user-supplied criteria. They do not access or expose private user profile data:

| Endpoint | HTTP Method | Scope | Authorization Rationale |
| :--- | :---: | :---: | :--- |
| `/api/health` | `GET` | System | Public liveness probe & aggregate dataset counts. |
| `/api/analytics/overview` | `GET` | Analytics | Macro-level hiring trends, role distributions. |
| `/api/analytics/market-overview`| `GET` | Analytics | Alias for market overview. |
| `/api/analytics/salary` | `GET` | Analytics | Disclosed salary distributions and percentiles. |
| `/api/skills/top` | `GET` | Analytics | High-demand skill rankings. |
| `/api/skills/categories` | `GET` | Analytics | Skill categories and aggregate demand. |
| `/api/skills/emerging` | `GET` | Analytics | Emerging skill momentum tiers. |
| `/api/jobs` | `GET` | Jobs | Job search, faceted filtering, pagination. |
| `/api/jobs/{job_id}` | `GET` | Jobs | Public job posting details. |
| `/api/salary/predict` | `POST` | ML Inference | Stateless salary estimation based on role & skills. |
| `/api/salary/metadata` | `GET` | ML Metadata | Supported feature metadata for salary UI. |
| `/api/classify/job` | `POST` | ML Inference | Stateless job role classification. |
| `/api/classify/batch` | `POST` | ML Inference | Batch job classification (up to 100 items). |
| `/api/classify/taxonomy` | `GET` | Taxonomy | Approved 11-role taxonomy definitions. |
| `/api/classify/info` | `GET` | ML Metadata | Classifier hyperparameters and version. |
| `/api/recommendations/roles` | `GET` | Recommendations | Supported technical career roles list. |
| `/api/skills/by-role` | `GET` | Recommendations | Role-specific benchmark skills. |
| `/api/recommendations/career` | `POST` | Compute | Stateless skill-fit ranking against benchmarks. |
| `/api/skills/gap` | `POST` | Compute | Differential skill gap analysis for given skills. |
| `/api/roadmap/generate` | `POST` | Compute | Milestone learning roadmap generation. |
| `/api/resume/extract-skills` | `POST` | In-Memory | Ephemeral PDF/DOCX resume text skill extraction. |
| `/api/auth/register` | `POST` | Auth | Public account creation. |
| `/api/auth/login` | `POST` | Auth | Public credential authentication. |

### 4.2 Protected Endpoints (State-Holding & User Profile Data)
These endpoints interact directly with individual user records, preferences, saved jobs, or sessions, and strictly require a valid Bearer token:

| Endpoint | HTTP Method | Security Control | Direct Access Without Token |
| :--- | :---: | :--- | :---: |
| `/api/auth/me` | `GET` | `validate_token(authorization)` | **HTTP 401 Unauthorized** |
| `/api/auth/profile` | `PUT` | `validate_token(authorization)` | **HTTP 401 Unauthorized** |
| `/api/auth/logout` | `POST` | `validate_token(authorization)` | **HTTP 401 Unauthorized** |

### 4.3 Why Direct Access to Protected UI is Prevented
Even though compute endpoints (like `/api/skills/gap`) accept arbitrary input payloads for developer flexibility and headless tests, **unauthenticated users cannot access the JobRadar web application interface**:
- The React Router hierarchy enforces `<ProtectedRoute>` across all app pages (`/dashboard`, `/jobs`, `/skills`, `/skill-gap`, `/mindmap`, `/profile`, `/onboarding`).
- Attempting to load any of these pages without an active session automatically redirects the browser to `/login`.
- If an unauthenticated user somehow attempts to invoke user-profile updates or read user state, the backend rejects it with 401.

---

## 5. Comprehensive Verification Results

### 5.1 Backend Test Execution
Command: `python -m unittest discover -s tests -p "test_*.py"`
- **Total Tests Collected:** **265** (250 original regression tests + 15 auth & security tests)
- **Passed:** **265**
- **Failed / Errors:** **0**
- **Execution Time:** **30.502 seconds**
- **Status:** **100% PASS**

#### Breakdown of Security Test Cases in `test_auth_api.py`:
1. `test_01_demo_login_success`: Valid login with demo user returns 200, valid Bearer token, and profile (**PASS**)
2. `test_02_login_invalid_password`: Wrong password returns 401 Unauthorized (**PASS**)
3. `test_03_login_nonexistent_user`: Non-existent username returns 401 Unauthorized (**PASS**)
4. `test_04_register_success`: Valid registration creates new user with `hasCompletedOnboarding=False` (**PASS**)
5. `test_05_register_duplicate_username`: Duplicate username rejected with 400 Bad Request (**PASS**)
6. `test_06_register_duplicate_email`: Duplicate email rejected with 400 Bad Request (**PASS**)
7. `test_07_register_invalid_email`: Malformed email rejected with 400 Bad Request (**PASS**)
8. `test_08_get_me_valid_token`: Valid Bearer token retrieves user profile (**PASS**)
9. `test_09_get_me_unauthorized`: Missing or bogus token returns 401 Unauthorized (**PASS**)
10. `test_10_update_profile`: Profile update persists to SQLite (**PASS**)
11. `test_11_logout_revokes_token`: Calling logout revokes session; subsequent requests fail with 401 (**PASS**)
12. `test_12_expired_session`: Past expiration timestamp returns 401 Unauthorized (**PASS**)
13. `test_13_password_complexity_validation`: Passwords under 8 chars or missing digits rejected with 400 (**PASS**)
14. `test_14_rate_limiting_brute_force`: 5 failed logins locks out IP with HTTP 429 Too Many Requests (**PASS**)
15. `test_15_production_demo_account_disabled`: Setting `JOBRADAR_ENV=production` blocks demo login with 403 (**PASS**)

### 5.2 Frontend Test Execution
Command: `npm test` (`node test_frontend_step7.mjs && node test_authentication_suite.mjs`)
- **Total Tests Collected:** **43** (29 component/integration tests + 14 auth guard tests)
- **Passed:** **43**
- **Failed / Errors:** **0**
- **Status:** **100% PASS**

### 5.3 Frontend Production Build
Command: `npm run build`
- **Output:**
  - `dist/index.html` (1.52 kB)
  - `dist/assets/index-D8jTBHQS.css` (40.28 kB)
  - `dist/assets/index-CBTGCYiS.js` (854.22 kB)
- **Status:** **BUILD SUCCESSFUL (0 errors in 2.21s)**

---

## 6. Remaining Limitations & Long-Term Hardening Recommendations

1. **HttpOnly Cookie Architecture (Future Enhancement):**
   - *Current Status:* Tokens reside in `localStorage`. While standard for modern decoupled SPAs, `localStorage` is accessible to JavaScript running in the same origin (posing theoretical risk if an XSS vulnerability were introduced).
   - *Recommendation:* In a future phase with a dedicated reverse proxy (e.g. Nginx or Traefik), transition token delivery to an `HttpOnly; Secure; SameSite=Lax` cookie.
2. **Distributed Rate Limiting:**
   - *Current Status:* Rate limiting is in-memory per FastAPI worker process.
   - *Recommendation:* If scaling across multiple horizontal Uvicorn worker processes or containers, back the rate limiter with a shared Redis instance.
3. **Multi-Factor Authentication (MFA):**
   - For administrative or privileged users, integrating Time-Based One-Time Passwords (TOTP) is recommended in future iterations.

---

## 7. Configuration Requirements for Production Hosting

To deploy JobRadar to production with full security enforcement:

```bash
# Set environment to production (automatically disables default demo account 'aarav_ds')
export JOBRADAR_ENV=production

# Explicitly ensure demo account is disabled (optional, defaulted to false in production)
export ALLOW_DEMO_ACCOUNT=false

# Increase PBKDF2 hashing rounds to OWASP recommendation
export PBKDF2_ROUNDS=600000

# Specify frontend hosting domain for CORS
export JOBRADAR_ALLOWED_ORIGINS="https://jobradar.yourdomain.com"

# Set backend API base URL for frontend build
export VITE_API_URL="https://api.jobradar.yourdomain.com"
```

---

## 8. Conclusion

The authentication and authorization architecture of JobRadar has been reviewed, hardened, and verified. The demo account vulnerability is fully mitigated for production, password policies and rate limiting are active, session lifecycles are enforced, and all 308 automated tests across frontend and backend pass cleanly without breaking any existing features.
