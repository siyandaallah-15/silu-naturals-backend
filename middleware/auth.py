"""
SiLu Naturals — auth helpers and JWT middleware
"""
import jwt, hashlib, os
from functools import wraps
from flask import request, jsonify

JWT_SECRET = os.environ.get("JWT_SECRET", "silu-naturals-super-secret-2026-change-in-prod")
JWT_ALGO   = "HS256"
JWT_EXP    = 60 * 60 * 8  # 8 hours


def hash_pw(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def make_token(payload: dict) -> str:
    import time
    payload["exp"] = int(time.time()) + JWT_EXP
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])


def require_auth(f):
    """Decorator — requires valid distributor JWT"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Unauthorised"}), 401
        try:
            data = decode_token(auth.split(" ", 1)[1])
            request.dist_code = data.get("code")
            request.token_data = data
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except Exception:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """Decorator — requires valid admin JWT"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Unauthorised"}), 401
        try:
            data = decode_token(auth.split(" ", 1)[1])
            if data.get("role") != "admin":
                return jsonify({"error": "Admin access required"}), 403
            request.admin_user = data.get("username")
        except Exception:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated
