"""
SiLu Naturals — Flask API Server
Run: python server.py
Production: gunicorn -w 4 -b 0.0.0.0:5000 server:app
"""
import os, sys
from flask import Flask, jsonify, request, send_from_directory

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(__file__))
from db.schema  import init_db
from db.seed    import seed
from routes.api import api

app = Flask(__name__, static_folder="public", static_url_path="")

@app.after_request
def add_cors(response):
    origin = request.headers.get("Origin", "*")
    response.headers["Access-Control-Allow-Origin"]  = origin
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Max-Age"]       = "86400"
    return response

@app.before_request
def handle_options():
    if request.method == "OPTIONS":
        from flask import Response
        return Response(status=200)

from collections import defaultdict
import time as _time
_rate_store = defaultdict(list)
RATE_LIMIT, RATE_WINDOW = 60, 60

@app.before_request
def rate_limit():
    if request.path.startswith("/api/auth"):
        ip  = request.remote_addr
        now = _time.time()
        _rate_store[ip] = [t for t in _rate_store[ip] if now - t < RATE_WINDOW]
        if len(_rate_store[ip]) >= RATE_LIMIT:
            return jsonify({"error": "Too many requests. Try again shortly."}), 429
        _rate_store[ip].append(now)

app.register_blueprint(api)

@app.route("/")
def index():
    pub = os.path.join(os.path.dirname(__file__), "public")
    if os.path.exists(os.path.join(pub, "index.html")):
        return send_from_directory(pub, "index.html")
    return jsonify({"app": "SiLu Naturals API", "docs": "/api/health"})

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error", "detail": str(e)}), 500

if __name__ == "__main__":
    print("=" * 55)
    print("  SiLu Naturals API Server")
    print("=" * 55)
    init_db()
    from db.schema import get_conn
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) as n FROM distributors").fetchone()["n"]
    conn.close()
    if count == 0:
        seed()
        print("[SEED] Demo data loaded")
    else:
        print(f"[DB] {count} distributors in database")
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG","false").lower() == "true"
    print(f"[SERVER] http://0.0.0.0:{port}  debug={debug}")
    app.run(host="0.0.0.0", port=port, debug=debug)
