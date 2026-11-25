# JobRadar — Comprehensive Authentication System Audit
**Document ID:** `JOBRADAR-AUTH-AUDIT-001`  
**Audit Date:** 2026-11-12  
**Target Systems:** JobRadar React Frontend (`Frontend/`) & FastAPI Backend (`DDS-Job-Market-Project/`)  
**Auditor:** Senior Full-Stack Engineer & Security QA Auditor  
**Status:** COMPLETE (FINDINGS & REPAIR SPECIFICATION)

---

## 1. Executive Summary

A comprehensive architectural and source code audit was conducted on the JobRadar application to determine why unauthenticated users can access protected application pages (such as the Dashboard, Jobs, Skills, Skill Gap, MindMap, and Profile) and why direct URL visits bypass the authentication flow.

The audit revealed a **dual root cause**:
1. **Frontend Mock Auto-Seeding (`src/api/auth.js`):** The `authApi.getProfile()` method automatically triggered `seedDefaultUser()`, which unconditionally injected a pre-built demo user session (`Aarav Sharma`, `usr-demo-01`) into `localStorage` whenever no session existed. On application mount, `AuthContext` called `getProfile()`, received this auto-seeded user, and set `isAuthenticated = true`.
2. **Missing Route Protection Architecture:** While `AppLayout.jsx` contained an unauthenticated check, `App.jsx` configured the root path `/` to redirect unconditionally to `/dashboard`. Furthermore, `/onboarding` was placed outside any route protection. The application lacked dedicated `<ProtectedRoute>` and `<PublicRoute>` guards, and `LoginPage.jsx` ignored the requested redirect destination (`location.state?.from`), sending all successful logins to `/dashboard`.
3. **Absence of Backend Authentication Endpoints:** The FastAPI backend (`src/job_market/api.py`) contained 21 analytical and inference endpoints but **zero authentication endpoints** (`/api/auth/*`) and no user persistence model in SQLite. The frontend `src/api/auth.js` had a developer comment noting that FastAPI auth integration was pending.

---

## 2. Detailed Inspection of Existing Authentication Implementation

### 2.1 Frontend Route Configuration (`Frontend/src/App.jsx`)
Inspection of `src/App.jsx` revealed the following route structure:
```jsx
<Routes>
  {/* Public Auth Routes */}
  <Route path="/login" element={<LoginPage />} />
  <Route path="/register" element={<RegisterPage />} />
  <Route path="/onboarding" element={<OnboardingPage />} />

  {/* Authenticated Dashboard & Feature Routes */}
  <Route element={<AppLayout />}>
    <Route path="/" element={<Navigate to="/dashboard" replace />} />
    <Route path="/dashboard" element={<DashboardPage />} />
    <Route path="/skills" element={<SkillsPage />} />
    <Route path="/jobs" element={<JobsPage />} />
    <Route path="/skill-gap" element={<SkillGapPage />} />
    <Route path="/mindmap" element={<MindMapPage />} />
    <Route path="/profile" element={<ProfilePage />} />
  </Route>

  {/* Fallback */}
  <Route path="*" element={<NotFoundPage />} />
</Routes>
```
**Vulnerabilities Identified:**
- `/onboarding` was treated as a public route. Any unauthenticated visitor entering `/onboarding` could view the career calibration quiz without a profile session.
- Root path `/` directly redirected to `/dashboard` without evaluating authentication state first.
- There was no `<PublicRoute>` guard for `/login` and `/register`. An authenticated user navigating to `/login` was presented with the login form again rather than being redirected to their active dashboard session.

### 2.2 Layout Guard & Session Handling (`Frontend/src/components/layout/AppLayout.jsx`)
`AppLayout.jsx` checked:
```javascript
if (loading) return <LoadingSpinner />;
if (!isAuthenticated) return <Navigate to="/login" state={{ from: location }} replace />;
```
While this guard was syntactically present, it was **completely bypassed** because `isAuthenticated` was always `true` on initial load due to `AuthContext` and `auth.js`.

### 2.3 The Auto-Seeding Defect (`Frontend/src/api/auth.js`)
Inspection of `src/api/auth.js` lines 19–54 identified the primary defect:
```javascript
const seedDefaultUser = () => {
  const existing = localStorage.getItem(STORAGE_KEY_USER);
  if (!existing) {
    const demoUser = {
      id: "usr-demo-01",
      name: "Aarav Sharma",
      username: "aarav_ds",
      email: "aarav@example.com",
      // ... full profile data ...
      hasCompletedOnboarding: true,
    };
    localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(demoUser));
    return demoUser;
  }
  try {
    return JSON.parse(existing);
  } catch {
    return null;
  }
};
```
When `authApi.getProfile()` was invoked by `AuthContext.jsx` on mount:
```javascript
async getProfile() {
  await new Promise((r) => setTimeout(r, 60));
  const user = seedDefaultUser();
  return { success: true, user };
}
```
**Consequences:**
1. Any fresh visitor, incognito window, or user with cleared storage immediately had `usr-demo-01` written to `localStorage`.
2. When a user clicked "Log Out", `localStorage.removeItem(STORAGE_KEY_USER)` ran and `user` was set to `null`. However, **refreshing the browser or opening a new tab immediately re-executed `seedDefaultUser()`**, silently logging the user back in as Aarav Sharma!
3. The mock `login(username, password)` function did not validate passwords at all. If a username was supplied, it constructed a mock user on the fly regardless of the password.
4. The mock `register(...)` function did not check whether a username or email was already registered in a database.

### 2.4 Login Redirection Defect (`Frontend/src/pages/LoginPage.jsx`)
In `LoginPage.jsx` lines 29–33:
```javascript
if (!res.user.hasCompletedOnboarding) {
  navigate("/onboarding");
} else {
  navigate("/dashboard");
}
```
`LoginPage` did not inspect `location.state?.from`. Even when `AppLayout` preserved the user's intended target (e.g. `/jobs` or `/skills`), the login handler discarded it and navigated directly to `/dashboard`.

### 2.5 Backend Authentication Status (`DDS-Job-Market-Project/src/job_market/`)
Inspection of the backend API routes registered in `src/job_market/api.py`:
- Total registered routes: 21
- Category endpoints: Analytics, Jobs, Skills, Emerging Momentum, Salary Prediction, Career Recommendations, Role Classification, Roadmap Generation, Resume Skill Extraction.
- Authentication endpoints (`/api/auth/*`): **0**
- User tables in `src/job_market/models.py`: **0** (Only `sources`, `ingestion_runs`, `raw_snapshots`, `jobs`, `job_versions`, `skills`, `job_skills`, `external_skill_benchmarks`, `external_salary_benchmarks`).
- The primary database (`data/jobradar.db`) is strictly a read-only job market intelligence dataset of 98,347 records and must never be altered.

---

## 3. Security & Architecture Audit Matrix

| Audit Checkpoint | Current Status | Vulnerability / Limitation | Required Resolution |
| :--- | :---: | :--- | :--- |
| **Initial Root Access** | ❌ FAILED | Visitors navigating to `/` bypass auth and land on `/dashboard`. | Guard `/` with auth check; redirect unauthenticated users to `/login`. |
| **Protected Routes** | ❌ FAILED | Direct access allowed because demo user auto-populates `localStorage`. | Eliminate automatic demo seeding on mount; require explicit login. |
| **Session Persistence** | ⚠️ PROVISIONAL | Only persists because of unvalidated `localStorage` string. | Validate token/session validity and expiration on application mount. |
| **Credential Validation** | ❌ FAILED | Any password accepted by frontend mock; no backend validation. | Implement backend `/api/auth/login` with real credential and hash checks. |
| **Account Registration** | ❌ FAILED | Saves mock profile to `localStorage`; no deduplication or hashing. | Implement backend `/api/auth/register` with uniqueness validation and secure hashing. |
| **Destination Memory** | ❌ FAILED | `location.state?.from` ignored upon login completion. | Inspect `state?.from` and redirect to original destination after login. |
| **Public Route Protection** | ❌ FAILED | Authenticated users can visit `/login` and `/register` repeatedly. | Implement `<PublicRoute>` to redirect authenticated sessions to `/dashboard`. |
| **Onboarding Protection** | ❌ FAILED | `/onboarding` is completely unprotected in `App.jsx`. | Place `/onboarding` under `<ProtectedRoute>` to require an authenticated session. |
| **Session Expiration** | ❌ FAILED | No expiration timestamp; sessions never expire or challenge the user. | Add token expiration timestamp and enforce 401 re-authentication. |
| **Logout Robustness** | ❌ FAILED | Logout works until page refresh, which triggers auto-seed. | Ensure logout completely purges tokens; page refresh stays on `/login`. |
| **Dataset Protection** | ✅ SAFE | Production database (`jobradar.db`) is completely intact. | Keep user/auth store completely isolated in dedicated `auth.db` store. |

---

## 4. Minimum Required Backend & Frontend Implementation Specification

To resolve all findings without breaking any existing features or altering production SQLite records, the following architecture is specified:

### 4.1 Backend Implementation (`src/job_market/auth_api.py`)
1. Create `auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])`.
2. Storage: Use an isolated SQLite database `data/auth_users.db` (or thread-safe persistent store) completely segregated from `data/jobradar.db`.
3. Pre-seed default demo account:
   - Username: `aarav_ds`
   - Password: `password123` (hashed via PBKDF2-SHA256 with cryptographic salt)
   - Profile: Data Scientist, completed onboarding, target skills.
4. Endpoints:
   - `POST /api/auth/register`: Validates uniqueness of username and email, hashes password, stores user, issues session token with expiration.
   - `POST /api/auth/login`: Authenticates username and password against stored PBKDF2 hash. Returns 401 on mismatch. Issues session token with expiration.
   - `GET /api/auth/me`: Validates `Authorization: Bearer <token>`, verifies expiration, returns user profile. Returns 401 if expired or invalid.
   - `PUT /api/auth/profile`: Validates Bearer token, updates user profile attributes (skills, targetRole, saved jobs).
   - `POST /api/auth/logout`: Revokes active session token.
5. Register `auth_router` in `src/job_market/api.py`.

### 4.2 Frontend Implementation
1. **Remove Auto-Seeding (`src/api/auth.js`):**
   - Eliminate `seedDefaultUser()` on initial mount.
   - If no token exists in storage, `getProfile()` returns `{ success: false, user: null }`.
   - Wire `authApi` methods to call the backend `/api/auth/*` endpoints via `request()` from `client.js`.
   - Store session token with expiration; validate before making requests.
2. **Centralized Route Guards (`src/components/common/ProtectedRoute.jsx`):**
   - `<ProtectedRoute>`: If loading, display loading spinner. If unauthenticated, `<Navigate to="/login" state={{ from: location }} replace />`. If user has not completed onboarding and path is not `/onboarding`, redirect to `/onboarding`.
   - `<PublicRoute>`: If loading, display loading spinner. If authenticated, `<Navigate to="/dashboard" replace />`.
3. **Route Structure in `App.jsx`:**
   - Wrap `/login` and `/register` with `<PublicRoute>`.
   - Wrap `/onboarding` and all dashboard/analytics features with `<ProtectedRoute>`.
   - Root `/` checks authentication: redirects to `/dashboard` if logged in, or `/login` if unauthenticated.
4. **Login Redirection in `LoginPage.jsx`:**
   - After successful authentication:
     ```javascript
     const destination = location.state?.from?.pathname || "/dashboard";
     const search = location.state?.from?.search || "";
     if (!res.user.hasCompletedOnboarding) {
       navigate("/onboarding");
     } else {
       navigate(`${destination}${search}`, { replace: true });
     }
     ```
   - Provide clear error notification if credentials are wrong.
5. **Autofill Demo Profile Button:**
   - Pre-fills `aarav_ds` and `password123` in form fields for quick 1-click testing, submitting to the actual credential validation backend.

---

## 5. Audit Conclusion

The authentication vulnerability in JobRadar was primarily caused by client-side simulation leftovers (`seedDefaultUser`) and the absence of a proper router guard hierarchy. Implementing real backend authentication endpoints in FastAPI backed by an isolated user store, combined with standard React Router route guards, will restore mandatory authentication across all 7 JobRadar pages with zero regression to existing ML models or dataset integrity.
