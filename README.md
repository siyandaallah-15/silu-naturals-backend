# SiLu Naturals — Backend & Deployment Guide

## Project Structure

```
silu-backend/
├── server.py              ← Main entry point (run this)
├── db/
│   ├── schema.py          ← SQLite table definitions
│   ├── seed.py            ← Demo data seeder
│   └── commission.py      ← Rank + commission logic
├── routes/
│   └── api.py             ← All REST API endpoints
├── middleware/
│   └── auth.py            ← JWT auth decorators
├── public/
│   └── index.html         ← Place your silu-naturals.html here (rename to index.html)
├── .env.example           ← Copy to .env and configure
├── requirements.txt       ← Python dependencies
└── README.md              ← This file
```

---

## Quick Start (Local)

### 1. Requirements
- Python 3.10+
- pip

### 2. Install dependencies
```bash
pip install flask pyjwt werkzeug
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your real values
```

### 4. Place the frontend
```bash
cp /path/to/silu-naturals.html public/index.html
```

### 5. Run the server
```bash
python server.py
```

The server starts on **http://localhost:5000**

---

## Deploying to a Real Host

### Option A — Render.com (Recommended, Free Tier)

1. Push this folder to a GitHub repository
2. Go to https://render.com → New Web Service
3. Connect your GitHub repo
4. Settings:
   - **Runtime:** Python 3
   - **Build Command:** `pip install flask pyjwt werkzeug`
   - **Start Command:** `gunicorn -w 2 -b 0.0.0.0:$PORT server:app`
5. Add Environment Variables in Render dashboard:
   - `JWT_SECRET` → your secret
   - `PORT` → 10000 (Render uses this)
6. Deploy — get your URL like `https://silu-naturals.onrender.com`

### Option B — Railway.app

1. Push to GitHub
2. New Project → Deploy from GitHub
3. Add environment variables
4. Railway auto-detects Python and runs `python server.py`

### Option C — VPS / Ubuntu Server

```bash
# Install dependencies
sudo apt install python3 python3-pip nginx -y
pip3 install flask pyjwt werkzeug gunicorn

# Run with gunicorn
gunicorn -w 4 -b 127.0.0.1:5000 server:app --daemon

# Nginx config (/etc/nginx/sites-available/silu)
server {
    listen 80;
    server_name yourdomain.co.za;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Option D — Heroku

```
# Procfile
web: gunicorn -w 2 server:app
```

---

## API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /api/auth/register | — | Register new distributor |
| POST | /api/auth/login | — | Login, get JWT |
| POST | /api/auth/admin-login | — | Admin login |
| GET | /api/distributor/profile | JWT | Own profile + maintenance status |
| GET | /api/distributor/stats | JWT | Dashboard stats |
| GET/POST | /api/distributor/sales | JWT | Sales history / log a sale |
| GET | /api/distributor/commissions | JWT | Commission ledger |
| GET | /api/distributor/team | JWT | Full recruit tree |
| GET/POST | /api/distributor/payouts | JWT | Request payout |
| GET | /api/distributor/maintenance | JWT | Maintenance status + history |
| POST | /api/distributor/maintenance/pay | JWT | Initiate maintenance payment |
| POST | /api/orders | — | Create a product order |
| POST | /api/orders/:no/confirm-payment | — | Confirm payment, trigger commissions |
| GET | /api/orders/:no | — | Get order details |
| GET | /api/referral/:code | — | Validate referral code |
| GET | /api/admin/distributors | Admin JWT | All distributors with status |
| POST | /api/admin/distributors/:code/suspend | Admin JWT | Suspend account |
| POST | /api/admin/distributors/:code/activate | Admin JWT | Activate account |
| GET | /api/admin/maintenance | Admin JWT | All maintenance statuses |
| POST | /api/admin/maintenance/:code/confirm | Admin JWT | Confirm maintenance payment |
| GET | /api/admin/payouts | Admin JWT | All payout requests |
| POST | /api/admin/payouts/:id/approve | Admin JWT | Approve payout |
| POST | /api/admin/payouts/:id/reject | Admin JWT | Reject payout |
| GET | /api/admin/orders | Admin JWT | All orders |
| GET | /api/admin/stats | Admin JWT | Business overview stats |
| GET | /api/health | — | Server health check |

---

## Frontend Integration

After deploying, update the API base URL in `silu-naturals.html`:

```javascript
const API_BASE = "https://your-deployed-url.com/api";
```

The frontend uses this constant for all API calls. When running locally,
set it to `http://localhost:5000/api`.

---

## Database

- **SQLite** — single file `silu.db`, created automatically on first run
- Tables: `distributors`, `recruits`, `orders`, `sales`, `commissions`,
  `maintenance_payments`, `payouts`, `admins`, `token_blacklist`
- For production with high traffic, migrate to **PostgreSQL**:
  ```bash
  pip install psycopg2-binary
  # Update get_conn() in db/schema.py to use psycopg2
  ```

---

## Security Checklist Before Going Live

- [ ] Change `JWT_SECRET` to a long random string
- [ ] Change admin password (`admin123` → something strong)
- [ ] Enable HTTPS (SSL certificate via Let's Encrypt)
- [ ] Set `FLASK_DEBUG=false`
- [ ] Restrict CORS to your domain only (in server.py)
- [ ] Back up `silu.db` regularly (or use PostgreSQL with automated backups)
- [ ] Set up email (SMTP) for order confirmation emails

---

## Commission Logic

Commissions are calculated automatically when an order is confirmed:

1. Sale amount = qty × R200
2. Walk up the sponsor chain (max 4 levels for Chairperson)
3. Each active sponsor earns their rank's commission rate on that level
4. Commissions are stored as `available` until a payout is requested
5. Admin approves payout → commissions marked as `paid`

Grace period (maintenance):
- 0–30 days since last payment → **Active**
- 1–7 days overdue → **Grace** (commissions paused, suspension warning shown)
- 8+ days overdue → **Suspended** (can be auto- or manually suspended)

---

*SiLu Naturals (Pty) Ltd — Port Elizabeth, Eastern Cape*
