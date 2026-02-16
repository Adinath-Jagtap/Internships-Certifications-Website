# 🚀 Internships & Certifications Hub

<div align="center">
  
[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.3+-black?logo=flask)](https://flask.palletsprojects.com)
[![MongoDB](https://img.shields.io/badge/MongoDB-6.0-green?logo=mongodb)](https://mongodb.com)
[![Cloudinary](https://img.shields.io/badge/Cloudinary-Image%20Upload-blue?logo=cloudinary)](https://cloudinary.com)
[![Render](https://img.shields.io/badge/Deployed%20on-Render-46E3B7?logo=render)](https://render.com)

**A community-driven platform to discover internships, certification courses, workshops, hackathons, and more — all in one place.**  
Built with Flask and MongoDB, featuring admin controls, image uploads, and ad tracking.

🌐 **[Live Demo](https://internships-certifications-website.onrender.com)**  

</div>

---

## 📚 Table of Contents

- [✨ Features](#-features)
- [⚙️ Tech Stack](#️-tech-stack)
- [📦 Requirements](#-requirements)
- [🚀 Quick Start](#-quick-start)
- [🔐 Environment Variables](#-environment-variables)
- [🗄️ Database & Indexes](#️-database--indexes)
- [📡 API Endpoints](#-api-endpoints)
- [☁️ Deployment Notes](#️-deployment-notes)
- [🛡️ Security Checklist](#️-security-checklist)
- [🎨 Upgrades & Enhancements](#-upgrades--enhancements)
- [🤝 Contributing](#-contributing)

---

## ✨ Features

✅ **Public Listings** – Browse internships, workshops, certification courses, hackathons, roadmaps, and external resources.  
✅ **Admin Dashboard** – Add, edit, delete content, and promote items as ads.  
✅ **User Authentication** – Register, log in, and manage sessions with secure password hashing.  
✅ **Image Uploads** – Seamless integration with Cloudinary for storing and serving images.  
✅ **Ad Tracking** – Impression and click tracking endpoints for analytics.  
✅ **Search & Pagination** – Global search across collections and paginated listings.  
✅ **Optimized Performance** – Rate limiting, caching, and response compression out of the box.

---

## ⚙️ Tech Stack

| **Category**       | **Technologies**                                                                               |
| ------------------ | ---------------------------------------------------------------------------------------------- |
| **Backend**        | Python 3.10+, Flask, PyMongo                                                                   |
| **Database**       | MongoDB (Atlas or self-hosted)                                                                 |
| **Image Storage**  | Cloudinary                                                                                     |
| **Extensions**     | Flask-CORS, Flask-Limiter, Flask-Caching, Flask-Compress                                       |
| **Frontend**       | HTML5, CSS3, JavaScript (vanilla – easily upgradable to modern frameworks)                     |
| **Deployment**     | Render (example), Gunicorn + Nginx recommended for production                                  |

---

## 📦 Requirements

- Python 3.10 or higher
- MongoDB instance (local or Atlas)
- Cloudinary account (free tier works)
- Git

All Python dependencies are listed in [`requirements.txt`](requirements.txt).

---

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/Adinath-Jagtap/Internships-Certifications-Website.git
cd Internships-Certifications-Website
```

### 2. Create and activate a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate          # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
Create a `.env` file in the project root (see [Environment Variables](#-environment-variables) for details).

### 5. Run the application
```bash
python app.py
```
Visit `http://localhost:5000` in your browser.

---

## 🔐 Environment Variables

Create a `.env` file with the following variables. **Never commit this file!**

| Variable                   | Description                                                              | Example                                                            |
| -------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `SECRET_KEY`               | Flask session secret (required in production)                            | `your-strong-secret-key`                                           |
| `MONGO_URI`                | MongoDB connection string                                                | `mongodb+srv://user:pass@cluster0.mongodb.net/community_platform`  |
| `CLOUDINARY_CLOUD_NAME`    | Cloudinary cloud name                                                    | `your_cloud_name`                                                  |
| `CLOUDINARY_API_KEY`       | Cloudinary API key                                                       | `your_api_key`                                                     |
| `CLOUDINARY_API_SECRET`    | Cloudinary API secret                                                    | `your_api_secret`                                                  |
| `ADMIN_USERNAME`           | Admin dashboard username (change default!)                               | `admin` (default)                                                  |
| `ADMIN_PASSWORD`           | Admin dashboard password (change default!)                               | `admin123` (default)                                                |
| `PORT`                     | Port for the Flask server (default: 5000)                                | `5000`                                                              |

---

## 🗄️ Database & Indexes

- The app connects to MongoDB using the `MONGO_URI` and expects a database named **`community_platform`** (adjustable in the connection string).
- Collections used:
  - `users`
  - `jobs_internships`
  - `workshops`
  - `courses`
  - `hackathons`
  - `roadmaps`
  - `websites`
  - `advertisements`
  - `ad_clicks`
- Indexes (e.g., unique email, text indexes, timestamp indexes) are automatically created on startup by `app.py` to optimize search and performance.

---

## 📡 API Endpoints

| Endpoint                         | Method | Description                                 |
| -------------------------------- | ------ | ------------------------------------------- |
| `/`                              | GET    | Homepage                                    |
| `/jobs`                          | GET    | Paginated jobs/internships                  |
| `/workshops`                     | GET    | Workshops listing                           |
| `/courses`                       | GET    | Courses listing                             |
| `/hackathons`                    | GET    | Hackathons listing                          |
| `/roadmaps`                      | GET    | Roadmaps listing                            |
| `/websites`                      | GET    | External resources listing                   |
| `/api/get-ads`                   | GET    | Retrieve active ads (randomized)            |
| `/ad/impression/<ad_id>`         | POST   | Record an ad impression                      |
| `/ad/click/<ad_id>`              | POST   | Record an ad click (saves to `ad_clicks`)    |
| `/api/search?q=<term>`           | GET    | Global search across all collections         |
| `/login`, `/register`, `/logout` | *      | Session‑based authentication endpoints       |

> ⚠️ **All routes and their exact behavior are defined in `app.py` – always check there for the latest implementations.**

---

## ☁️ Deployment Notes

- Use a managed MongoDB (like [MongoDB Atlas](https://www.mongodb.com/atlas)) for production.
- Set all required environment variables in your hosting provider (Render, Heroku, etc.).
- The app expects a `PORT` environment variable on most PaaS platforms.
- **Do not use `app.run()` in production** – deploy with a production WSGI server like Gunicorn behind a reverse proxy (Nginx).
- Example Gunicorn command:
  ```bash
  gunicorn -w 4 -b 0.0.0.0:$PORT app:app
  ```

---

## 🛡️ Security Checklist

- [ ] **Change default admin credentials** (`ADMIN_USERNAME` / `ADMIN_PASSWORD`).
- [ ] **Use a strong `SECRET_KEY`** (generate with `os.urandom(24)`).
- [ ] **Enable HTTPS** and set secure cookie flags (`SESSION_COOKIE_SECURE=True`, `SESSION_COOKIE_HTTPONLY=True`).
- [ ] **Create a MongoDB user with least‑privilege permissions** (read/write only to required collections).
- [ ] **Validate and sanitize all user inputs** (forms, file uploads).
- [ ] **Limit file upload sizes** and verify images before sending to Cloudinary.
- [ ] **Monitor rate‑limiting** (configured via Flask-Limiter) and set up alerts for suspicious activity.
- [ ] **Keep dependencies updated** – regularly run `pip-audit` or similar tools.

---

## 🎨 Upgrades & Enhancements

To transform this project into a truly modern, eye‑catching platform, consider implementing these improvements:

### Frontend
- **CSS Framework** – Replace vanilla CSS with **Tailwind CSS** or **Bootstrap 5** for a sleek, responsive design.
- **Component‑based UI** – Introduce a lightweight frontend framework like **Alpine.js** or **Vue.js** for dynamic components (search, modals, infinite scroll).
- **Animations** – Add subtle scroll animations using **AOS (Animate on Scroll)** or **GSAP**.
- **Dark Mode** – Implement a theme toggle with CSS variables.
- **Icons** – Use **Font Awesome** or **Heroicons** for consistent, modern icons.

### Backend & Performance
- **API Blueprint** – Refactor `app.py` into Flask Blueprints for better maintainability.
- **Caching** – Implement Redis for session storage and advanced caching (beyond Flask-Caching’s simple cache).
- **Search** – Replace basic text search with **Elasticsearch** or **MongoDB Atlas Search** for better relevance.
- **File Uploads** – Add image preview and cropping before upload.

### DevOps & CI/CD
- **Testing** – Add unit and integration tests (pytest) and run them via GitHub Actions.
- **Containerization** – Provide a `Dockerfile` and `docker-compose.yml` for easy local development and deployment.
- **Monitoring** – Integrate an error tracker like **Sentry** and performance monitoring with **New Relic**.

### Additional Features
- **Email Notifications** – Notify users about new opportunities matching their interests.
- **Social Login** – Allow sign‑in with Google/GitHub for smoother onboarding.
- **Bookmarking** – Let users save their favorite listings.
- **Comments/Ratings** – Enable community feedback on opportunities.

---

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. **Fork** the repository.
2. Create a **feature branch**: `git checkout -b feat/your-feature`.
3. **Commit** your changes with clear messages.
4. **Push** to your branch and open a **Pull Request**.

Please ensure your code follows existing style conventions and includes appropriate comments. For major changes, open an issue first to discuss what you'd like to change.

---

<div align="center">
  
  **Made with ❤️ by [Adinath Jagtap](https://github.com/Adinath-Jagtap)**  
  ⭐ Star this repo if you find it useful!  
  [Report Bug](https://github.com/Adinath-Jagtap/Internships-Certifications-Website/issues) · [Request Feature](https://github.com/Adinath-Jagtap/Internships-Certifications-Website/issues)

</div>

---
