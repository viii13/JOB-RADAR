# JobRadar — Production Deployment Guide

This guide walks you through deploying **JobRadar** to the internet as a live, secure, production-grade website with a custom domain and SSL.

---

## Architecture Overview in Production

JobRadar is built as a unified full-stack platform:
* **Frontend:** React 19 + Tailwind CSS + Recharts Single-Page Application (SPA)
* **Backend:** Python FastAPI service serving 21 REST API endpoints
* **Datastore:** In-memory optimized DataFrame search across 97,682 verified Indian postings + SQLite database
* **ML Engines:** TF-IDF + Logistic Regression Classifier, Conformal Ridge Salary Regressor, and Skill-Gap Recommendation Matrix

In production, **FastAPI automatically serves the compiled frontend bundle** from `Frontend/dist`, so the entire application runs on a **single port (8000)** without complex reverse proxying!

---

## Option 1: 1-Click Deployment on Render.com (Recommended & Free Tier Available)

[Render](https://render.com) supports automated Docker and Python deployments directly from GitHub.

### Step 1: Push Project to GitHub
1. Create a new repository on [GitHub](https://github.com): `jobradar`
2. Initialize git and push:
```bash
git init
git add .
git commit -m "feat: complete JobRadar production platform"
git branch -M main
git remote add origin https://github.com/<your-username>/jobradar.git
git push -u origin main
```

### Step 2: Create Web Service on Render
1. Log in to [dashboard.render.com](https://dashboard.render.com).
2. Click **New +** → **Web Service**.
3. Select your GitHub repository.
4. Set the configuration:
   * **Name:** `jobradar`
   * **Region:** Singapore / Frankfurt / Oregon
   * **Language / Environment:** `Docker`
   * **Dockerfile Path:** `./Dockerfile`
   * **Instance Type:** `Free` or `Starter` (recommended for faster in-memory model loading)
5. Under **Environment Variables**, add:
   * `PORT`: `8000`
   * `PYTHONPATH`: `/app/backend/src`
6. Click **Create Web Service**.
7. Render will build the Docker container and provide a live HTTPS URL:
   `https://jobradar.onrender.com`

---

## Option 2: 1-Click Deployment on Railway.app

[Railway](https://railway.app) provides ultra-fast Docker deployments with generous resources.

1. Install Railway CLI or log in to the web dashboard.
2. Click **New Project** → **Deploy from GitHub repo**.
3. Railway automatically detects `Dockerfile` and builds both the React frontend and FastAPI backend.
4. In **Settings** → **Networking**, click **Generate Domain**.
5. Your app will be live at `https://jobradar.up.railway.app`.

---

## Option 3: Local Docker Self-Hosting

You can run the production-compiled container on your own machine or on any VPS (AWS EC2, DigitalOcean Droplet, Hetzner, Linode) using Docker Compose:

```bash
# Build and start container
docker compose up -d --build

# Verify status
docker compose ps

# Check logs
docker compose logs -f
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Custom Domain Setup (e.g. `jobradar.in` or `jobradar.ai`)

Once your app is deployed to Render or Railway:
1. Buy your domain name from **Namecheap**, **GoDaddy**, or **Cloudflare** (e.g., `jobradar.in` costs ~₹499/year).
2. In your Render / Railway dashboard, go to **Settings** → **Custom Domains**.
3. Add your domain: `jobradar.in` and `www.jobradar.in`.
4. Add the DNS records in your domain registrar:
   * **CNAME Record:** `www` pointing to `jobradar.onrender.com`
   * **ANAME / ALIAS or A Record:** pointing to the IP provided by Render.
5. Render/Railway will automatically issue a **free Let's Encrypt SSL certificate (HTTPS)** within 10 minutes.

---

## Production Security & Environment Checklist

- [x] CORS configured for production domain
- [x] In-memory resume extraction (0 temporary disk persistence)
- [x] Conformal prediction intervals bound to empirical training distributions
- [x] SPA client-side fallback routes mounted cleanly on `/{full_path}`
- [x] Dockerfile healthcheck configured on `/api/health`
