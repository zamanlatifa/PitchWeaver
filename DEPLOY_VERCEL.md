# Deploying PitchWeaver on Vercel

## 1. Create a free Postgres database
Vercel can't keep a SQLite file, so the app needs a hosted database.
- Go to https://neon.tech (or use Vercel → Storage → Neon), create a project.
- Copy the connection string, e.g. `postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require`

Tables are created automatically on first start.

## 2. Push this folder to GitHub
The `.gitignore` already keeps `.env` and `*.db` out of the repo.

```bash
git init
git add .
git commit -m "PitchWeaver"
git branch -M main
git remote add origin https://github.com/<you>/pitchweaver.git
git push -u origin main
```

## 3. Import into Vercel
vercel.com → Add New → Project → pick the repo.
- Framework preset: **Other**
- Leave the build and output settings empty (`vercel.json` handles it)

Under **Environment Variables**, add:

| Name | Value |
|---|---|
| `DATABASE_URL` | your Neon connection string |
| `JWT_SECRET_KEY` | output of `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | your Gmail address |
| `SMTP_PASSWORD` | a **new** Gmail app password |
| `SMTP_FROM` | your Gmail address |

Click **Deploy**.

## What changed from the original
- `api/index.py` + `vercel.json`: run the Flask app as a Vercel function.
- `Backend/app.py`: reads `DATABASE_URL` (Postgres) and loads `.env` locally.
- `requirements.txt`: added `psycopg2-binary` for Postgres.
- `.gitignore` / `.vercelignore`: keep secrets and the local DB out.
- `Backend/.env.example`: real password replaced with placeholders.

Locally, `python Backend/app.py` still works with SQLite as before.
