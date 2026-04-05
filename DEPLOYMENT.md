# Deployment Guide

This project has two Flask services:
- Public dashboard service (`web_app.py`)
- Admin portal service (`admin_app.py`)

For cloud deployment, run them as separate web services that share the same MongoDB database.

## 1. Prepare MongoDB

Use MongoDB Atlas (recommended) or another reachable MongoDB instance.

Get:
- `MONGO_URI` (connection string)
- Database name (default used here is `relief_system`)

## 2. Deploy on Render (recommended)

This repository includes `render.yaml` to create both services automatically.

1. Push this project to GitHub.
2. In Render, choose "New" -> "Blueprint".
3. Select your repository.
4. Render reads `render.yaml` and proposes two services:
   - `aiac-web`
   - `aiac-admin`
5. Set required secret environment variables:
   - For `aiac-web`:
     - `MONGO_URI`
     - `WEB_APP_SECRET_KEY`
   - For `aiac-admin`:
     - `MONGO_URI`
     - `ADMIN_APP_SECRET_KEY`
     - `ADMIN_PASSWORD`
6. Deploy.

## 3. Local Production-like Run (optional)

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run web app with Gunicorn:

```powershell
gunicorn --bind 0.0.0.0:5000 wsgi_web:app
```

Run admin app with Gunicorn:

```powershell
gunicorn --bind 0.0.0.0:5001 wsgi_admin:app
```

Note: On Windows, Gunicorn is not supported for native production use. For local Windows testing, use:

```powershell
python web_app.py
python admin_app.py
```

## 4. Required Environment Variables

Copy `.env.example` values into your platform environment settings:

- `MONGO_URI`
- `MONGO_DB_NAME`
- `WEB_APP_SECRET_KEY`
- `ADMIN_APP_SECRET_KEY`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`

## 5. Security Checklist

- Set strong random values for both app secret keys.
- Change default admin password before public launch.
- Restrict admin portal access if possible (IP allowlist/basic auth/reverse proxy rule).
- Use HTTPS (Render provides this automatically).
