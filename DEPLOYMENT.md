# SiLu Naturals — Backend Deployment Guide

## What You're Getting

| File | Purpose |
|------|---------|
| `server.py` | Main Flask server — run this to start everything |
| `db/schema.py` | SQLite database schema (auto-creates on startup) |
| `db/seed.py` | Demo data — 9 distributors, sales, commissions |
| `db/commission.py` | Rank engine + multi-level commission calculator |
| `routes/api.py` | All REST API endpoints |
| `middleware/auth.py` | JWT authentication + admin guards |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment config template |

---

## Quick Start (Local Testing)

```bash
# 1. Install Python dependencies
pip install flask pyjwt python-dotenv

# 2. Copy environment config
cp .env.example .env
# Edit .env — at minimum change JWT_SECRET

# 3. Start the server
python server.py

# Server runs on http://localhost:5000
# API docs: http://localhost:5000/api/health
```

---

## Connecting the Frontend

Open `silu-naturals.html` and find this line near the bottom:

```javascript
const SILU_API_BASE = '';   // ← UPDATE THIS when hosting
```

Change it to your server URL:

```javascript
const SILU_API_BASE = 'https://api.silunaturals.co.za';
```

Also copy `silu-naturals.html` into the `public/` folder so Flask can serve it:
```bash
cp silu-naturals.html silu-backend/public/index.html
```

---

## Hosting Options

### Option A — VPS / Cloud Server (Recommended)
Best for: full control, cheapest long-term

**Providers:** DigitalOcean Droplet (R120/mo), Render.com (free tier), Railway.app

```bash
# On your server:
git clone your-repo
cd silu-backend
pip install flask pyjwt gunicorn python-dotenv
cp .env.example .env
nano .env  # set your JWT_SECRET and other values

# Run with Gunicorn (production WSGI server)
gunicorn -w 4 -b 0.0.0.0:5000 server:app

# Or use systemd to keep it running:
# sudo nano /etc/systemd/system/silu.service
```

**Systemd service file** (`/etc/systemd/system/silu.service`):
```ini
[Unit]
Description=SiLu Naturals API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/silu-backend
Environment=PORT=5000
ExecStart=/usr/bin/gunicorn -w 4 -b 0.0.0.0:5000 server:app
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable silu
sudo systemctl start silu
```

### Option B — Render.com (Free, Easy)

1. Push code to GitHub
2. Go to render.com → New → Web Service
3. Connect your GitHub repo
4. Set:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn -w 2 -b 0.0.0.0:$PORT server:app`
   - **Environment Variables:** Add `JWT_SECRET`, `PORT=10000`
5. Deploy → copy the URL → paste into `SILU_API_BASE` in the HTML

### Option C — Same Server (Simplest)
Serve the HTML directly from Flask by placing it in `public/index.html`.
Then everything runs from one URL with no CORS issues.

---

## Nginx Reverse Proxy (VPS)

```nginx
server {
    listen 80;
    server_name api.silunaturals.co.za;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 60;
    }
}
```

Add SSL with Certbot:
```bash
sudo certbot --nginx -d api.silunaturals.co.za
```

---

## API Endpoints Reference

### Public
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Server health check |
| GET | `/api/referral/{code}` | Look up referral code |
| POST | `/api/orders` | Place a product order |
| POST | `/api/orders/{no}/confirm-payment` | Mark order as paid |

### Distributor (requires JWT)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new distributor |
| POST | `/api/auth/login` | Distributor login |
| GET | `/api/distributor/profile` | Get own profile |
| GET | `/api/distributor/stats` | Dashboard stats |
| GET/POST | `/api/distributor/sales` | View / log sales |
| GET | `/api/distributor/commissions` | Commission ledger |
| GET | `/api/distributor/team` | Team tree |
| GET/POST | `/api/distributor/payouts` | Payouts |
| GET | `/api/distributor/maintenance` | Maintenance status |
| POST | `/api/distributor/maintenance/pay` | Initiate maintenance payment |

### Admin (requires admin JWT)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/admin-login` | Admin login |
| GET | `/api/admin/distributors` | All distributors |
| POST | `/api/admin/distributors/{code}/suspend` | Suspend account |
| POST | `/api/admin/distributors/{code}/activate` | Activate account |
| GET | `/api/admin/maintenance` | All maintenance statuses |
| POST | `/api/admin/maintenance/{code}/confirm` | Confirm maintenance payment |
| GET | `/api/admin/payouts` | All payout requests |
| POST | `/api/admin/payouts/{id}/approve` | Approve payout |
| POST | `/api/admin/payouts/{id}/reject` | Reject payout |
| GET | `/api/admin/orders` | All orders |
| GET | `/api/admin/stats` | Business overview stats |

---

## Default Login Credentials

| Account | Username | Password |
|---------|----------|----------|
| Admin | admin | admin123 |
| Demo distributor | thandi@demo.com | demo1234 |

**⚠️ Change these immediately after first login in production.**

---

## Database

- SQLite file: `silu.db` (created automatically in the project folder)
- For production with many concurrent users, migrate to PostgreSQL
- Back up `silu.db` daily: `cp silu.db silu.db.backup.$(date +%F)`

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port | 5000 |
| `JWT_SECRET` | **Must change** — signs all tokens | insecure default |
| `DB_PATH` | SQLite database path | `./silu.db` |
| `FLASK_DEBUG` | Enable debug mode | false |
| `FRONTEND_URL` | Your site URL for CORS | * |

---

## Production Checklist

- [ ] Change `JWT_SECRET` to a random 64-character string
- [ ] Change admin password
- [ ] Set `FLASK_DEBUG=false`
- [ ] Set up Nginx + SSL certificate (HTTPS)
- [ ] Set up daily database backups
- [ ] Update `SILU_API_BASE` in the HTML file to your domain
- [ ] Copy `silu-naturals.html` to `public/index.html`
- [ ] Test all endpoints with Postman or curl

---

## Support

WhatsApp: 072 624 5237  
Email: silu.naturals@gmail.com
