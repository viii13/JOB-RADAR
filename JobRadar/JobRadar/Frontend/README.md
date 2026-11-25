# JOBRADAR

> **"Spot the skills. Find the opportunities."**

JOBRADAR is a desktop-first Data Science & career intelligence platform designed for students, fresh graduates, and career changers. It bridges the gap between labor market requirements and candidate skill readiness through real-time demand telemetry, customized gap diagnosis, and interactive skill exploration.

---

## 🌟 Key Features

1. **Personalized Career Dashboard (`/dashboard`)**
   - High-level KPIs: Jobs Analyzed, Average CTC (₹ LPA), Most In-Demand Skill, User Skill Match Rate.
   - Core visual telemetry: Top Skills Right Now (horizontal bar) and Top Indian Tech Corridors.
   - Tailored **"Your Skill Gap"** diagnosis preview & **"Recommended Next Move"** action card.

2. **Skill Analytics & Intelligence (`/skills`)**
   - Ranked technical skills with demand frequencies and category badges.
   - Role-specific skill distributions (switchable between Data Scientist, ML Engineer, Data Analyst, Data Engineer, GenAI Engineer).

3. **Job Explorer (`/jobs`)**
   - 105+ realistic job records covering Bangalore, Hyderabad, Pune, Gurgaon, Mumbai, and Remote.
   - Live search by title, company, tech stack, or location.
   - Deep filters: Role, Location, Work Mode (Remote / Hybrid / On-site), Experience, Minimum Salary (₹ LPA), Sort Order.
   - **"Jobs you might actually match"** personalized highlight banner with match percentage algorithms.
   - Full slide-out **Job Detail Modal** comparing matched skills (✓) vs missing skills with "Save Job" and "Analyze Skill Gap" actions.

4. **My Skill Gap Analysis (`/skill-gap`)**
   - Direct differential analysis between active user skills and the benchmark requirements of the chosen target role.
   - Priority-ranked cards (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
   - Detailed demand metrics (e.g. "Appears in 74% of relevant postings").
   - Clear explanations of why each skill matters with one-click navigation to matching jobs.

5. **Interactive Skill Mind Map (`/mindmap`)**
   - Visual hierarchical tree showing prerequisites, core competencies, and tooling paths for each role.

6. **Profile & Bookmarks (`/profile`)**
   - Editable credentials, education details, career vision statement, and target role switcher.
   - Interactive active skills inventory (add and remove skills on the fly).
   - Bookmarked jobs list with one-click detail viewing and deletion.

7. **8-Step Career Calibration Quiz (`/onboarding`)**
   - Multi-step questionnaire collecting personal details, academic standing, experience level, target role, skill tags, vision, and preferences.

---

## 🛠️ Tech Stack

- **Framework:** React 19 + Vite 8
- **Styling:** Tailwind CSS (Custom Modern Palette)
- **Routing:** React Router v7
- **Data Visualization:** Recharts
- **Icons:** Lucide React
- **Celebration Animations:** Canvas Confetti

---

## 📁 Systematic Project Architecture

```
Frontend/
├── public/
├── src/
│   ├── api/                     <-- Clean API Service Layer (FastAPI Ready)
│   │   ├── auth.js              # /auth/login, /auth/register, /user/profile
│   │   ├── jobs.js              # /jobs, /jobs/{id}
│   │   ├── skills.js            # /api/skills/top, role breakdown
│   │   ├── analytics.js         # /api/health, /api/skills/categories, /api/analytics/salary
│   │   └── recommendations.js   # /skills/gap, skill resources
│   ├── components/
│   │   ├── common/              # KpiCard, ChartCard, SkillBadge, ProgressBar, EmptyState, LoadingState
│   │   ├── layout/              # Sidebar, TopNavbar, AppLayout
│   │   ├── jobs/                # JobCard, JobDetailModal, JobFilterBar
│   │   ├── mindmap/             # InteractiveMindMap
│   │   └── skills/              # SkillGapCard
│   ├── context/
│   │   ├── AuthContext.jsx      # Session management, persistence & user actions
│   │   └── ToastContext.jsx     # Floating toast notification system
│   ├── data/
│   │   ├── mockJobs.js          # 105+ detailed tech job records
│   │   ├── mockAnalytics.js     # Market summary & role demand data
│   │   ├── mockLearning.js      # Curated resources & project prompts for gap analysis
│   │   └── mindMapData.js       # Interactive skill graph datasets
│   ├── pages/                   # Clean active page routes
│   │   ├── DashboardPage.jsx    # Overview dashboard
│   │   ├── SkillsPage.jsx       # Skill demand & role distribution
│   │   ├── JobsPage.jsx         # Job explorer & filter workbench
│   │   ├── SkillGapPage.jsx     # Personalized gap diagnosis
│   │   ├── MindMapPage.jsx      # Interactive skill mindmap
│   │   ├── ProfilePage.jsx      # Profile & bookmarks
│   │   ├── OnboardingPage.jsx   # Calibration quiz
│   │   ├── LoginPage.jsx        # Login authentication
│   │   ├── RegisterPage.jsx     # Registration
│   │   └── NotFoundPage.jsx     # 404 handler
│   ├── App.jsx                  # Route definitions
│   ├── index.css                # Tailwind directives & utility classes
│   └── main.jsx                 # Entrypoint
├── index.html                   # Fonts (Plus Jakarta Sans + Outfit) & SEO metadata
├── package.json
├── tailwind.config.js
└── vite.config.js
```
