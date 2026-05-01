"""
SiLu Naturals — API routes
All endpoints for auth, distributors, orders, commissions, maintenance, admin.
"""
from flask import Blueprint, request, jsonify
import hashlib, uuid
from datetime import datetime

from db.schema    import get_conn
from db.commission import get_rank, get_maintenance_status, compute_commissions, \
                          PACK_PRICES, PACK_CONTENTS, PRODUCT_PRICE, SHIPPING_FEE
from middleware.auth import hash_pw, make_token, require_auth, require_admin

api = Blueprint("api", __name__, url_prefix="/api")


# ──────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────
def row_to_dict(row):
    return dict(row) if row else None


def dist_public(d: dict, conn) -> dict:
    """Return safe distributor dict with rank + maintenance info."""
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM recruits WHERE sponsor_code=?", (d["code"],)
    ).fetchone()
    direct = row["cnt"] if row else 0
    rank = get_rank(direct)
    ms = get_maintenance_status(d, conn)
    return {
        "code":       d["code"],
        "fname":      d["fname"],
        "lname":      d["lname"],
        "email":      d["email"],
        "phone":      d["phone"],
        "city":       d["city"],
        "pack":       d["pack"],
        "status":     ms["status"],
        "join_date":  d["join_date"],
        "rank":       rank["name"],
        "commission_rate": rank["rate"],
        "maintenance_fee": ms["fee"],
        "next_due":   ms["next_due"],
        "days_overdue": ms["days_overdue"],
        "sponsor_code": d["sponsor_code"],
        "direct_recruits": direct,
    }


# ──────────────────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────────────────
@api.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    required = ["fname","lname","email","phone","id_number","city","pack","password"]
    for f in required:
        if not data.get(f, "").strip():
            return jsonify({"error": f"Field '{f}' is required."}), 400

    if len(data["id_number"]) != 13 or not data["id_number"].isdigit():
        return jsonify({"error": "ID number must be exactly 13 digits."}), 400
    if data["pack"] not in PACK_PRICES:
        return jsonify({"error": "Invalid pack. Choose Silver, Gold, or Platinum."}), 400
    if len(data["password"]) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    conn = get_conn()
    # Check duplicate email
    if conn.execute("SELECT 1 FROM distributors WHERE email=?", (data["email"],)).fetchone():
        conn.close()
        return jsonify({"error": "Email already registered."}), 409

    # Generate unique code
    base = (data["fname"][:6] + "001").upper().replace(" ", "")
    code = base
    counter = 1
    while conn.execute("SELECT 1 FROM distributors WHERE code=?", (code,)).fetchone():
        counter += 1
        code = base[:-len(str(counter))] + str(counter)

    sponsor_code = data.get("referral_code", "").strip().upper() or None
    if sponsor_code and not conn.execute(
        "SELECT 1 FROM distributors WHERE code=?", (sponsor_code,)
    ).fetchone():
        conn.close()
        return jsonify({"error": f"Referral code '{sponsor_code}' not found."}), 404

    today = datetime.utcnow().strftime("%Y-%m-%d")
    conn.execute("""
        INSERT INTO distributors
        (code,fname,lname,email,phone,id_number,city,pack,sponsor_code,password_hash,
         status,join_date,rank_name)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        code, data["fname"].strip(), data["lname"].strip(),
        data["email"].strip().lower(), data["phone"].strip(),
        data["id_number"].strip(), data["city"].strip(),
        data["pack"], sponsor_code,
        hash_pw(data["password"]), "pending", today, "Unranked"
    ))

    if sponsor_code:
        conn.execute(
            "INSERT OR IGNORE INTO recruits(sponsor_code,recruit_code) VALUES(?,?)",
            (sponsor_code, code)
        )

    conn.commit()

    # Generate registration order so they get sent to payment
    order_no = f"REG-{code}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    pack_price = PACK_PRICES[data["pack"]]
    conn.execute("""
        INSERT INTO orders
        (order_no,customer_name,customer_phone,customer_email,pep_store,
         product,qty,unit_price,subtotal,shipping,total,
         payment_method,payment_status,order_type,dist_code)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        order_no,
        f"{data['fname']} {data['lname']}",
        data["phone"], data["email"].lower(),
        "N/A",
        f"{data['pack']} Registration Pack",
        1, pack_price, pack_price, 0, pack_price,
        "pending", "pending", "registration", code
    ))
    conn.commit()
    conn.close()

    token = make_token({"code": code, "email": data["email"].lower(), "role": "distributor"})
    return jsonify({
        "success": True,
        "code":    code,
        "token":   token,
        "order_no": order_no,
        "pack":    data["pack"],
        "amount":  pack_price,
        "message": "Registration successful. Proceed to payment."
    }), 201


@api.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM distributors WHERE email=?", (email,)
    ).fetchone()
    conn.close()
    if not row or row["password_hash"] != hash_pw(password):
        return jsonify({"error": "Invalid email or password."}), 401

    d = dict(row)
    conn = get_conn()
    profile = dist_public(d, conn)
    conn.close()
    token = make_token({"code": d["code"], "email": email, "role": "distributor"})
    return jsonify({"success": True, "token": token, "distributor": profile})


@api.route("/auth/admin-login", methods=["POST"])
def admin_login():
    data = request.get_json(force=True)
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM admins WHERE username=?", (data.get("username", ""),)
    ).fetchone()
    conn.close()
    if not row or row["password_hash"] != hash_pw(data.get("password", "")):
        return jsonify({"error": "Invalid admin credentials."}), 401
    token = make_token({"username": row["username"], "role": "admin"})
    return jsonify({"success": True, "token": token})


# ──────────────────────────────────────────────────────────
# DISTRIBUTOR — self
# ──────────────────────────────────────────────────────────
@api.route("/distributor/profile", methods=["GET"])
@require_auth
def get_profile():
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM distributors WHERE code=?", (request.dist_code,)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    profile = dist_public(dict(row), conn)
    conn.close()
    return jsonify(profile)


@api.route("/distributor/stats", methods=["GET"])
@require_auth
def get_stats():
    code = request.dist_code
    conn = get_conn()
    row = conn.execute("SELECT * FROM distributors WHERE code=?", (code,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404

    d = dict(row)
    ms = get_maintenance_status(d, conn)

    # Sales totals
    sales = conn.execute(
        "SELECT SUM(amount) as total, SUM(qty) as units FROM sales WHERE dist_code=?", (code,)
    ).fetchone()

    # Commissions
    comms = conn.execute(
        "SELECT SUM(commission) as total FROM commissions WHERE beneficiary=? AND status='available'",
        (code,)
    ).fetchone()
    earned = conn.execute(
        "SELECT SUM(commission) as total FROM commissions WHERE beneficiary=?", (code,)
    ).fetchone()

    # Team size (direct recruits)
    team = conn.execute(
        "SELECT COUNT(*) as cnt FROM recruits WHERE sponsor_code=?", (code,)
    ).fetchone()

    # Paid out
    paid_out = conn.execute(
        "SELECT SUM(amount) as total FROM payouts WHERE dist_code=? AND status='approved'",
        (code,)
    ).fetchone()

    conn.close()
    return jsonify({
        "maintenance":     ms,
        "personal_sales":  sales["total"] or 0,
        "units_sold":      sales["units"] or 0,
        "available_balance": comms["total"] or 0,
        "total_earned":    earned["total"] or 0,
        "paid_out":        paid_out["total"] or 0,
        "team_size":       team["cnt"] or 0,
    })


@api.route("/distributor/sales", methods=["GET","POST"])
@require_auth
def distributor_sales():
    code = request.dist_code
    conn = get_conn()
    if request.method == "POST":
        data = request.get_json(force=True)
        product = data.get("product","").strip()
        qty = int(data.get("qty", 1))
        amount = qty * PRODUCT_PRICE
        conn.execute(
            "INSERT INTO sales(dist_code,product,qty,amount) VALUES(?,?,?,?)",
            (code, product, qty, amount)
        )
        # Calculate commissions up the chain
        commissions = compute_commissions(amount, code, conn)
        for c in commissions:
            conn.execute("""
                INSERT INTO commissions(beneficiary,source_code,level,rate,sale_amount,commission,status)
                VALUES(?,?,?,?,?,?,'available')
            """, (c["beneficiary"], c["source_code"], c["level"],
                  c["rate"], c["sale_amount"], c["commission"]))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "amount": amount, "commissions_triggered": len(commissions)})

    rows = conn.execute(
        "SELECT * FROM sales WHERE dist_code=? ORDER BY sale_date DESC", (code,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@api.route("/distributor/commissions", methods=["GET"])
@require_auth
def distributor_commissions():
    code = request.dist_code
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM commissions WHERE beneficiary=? ORDER BY created_at DESC", (code,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@api.route("/distributor/team", methods=["GET"])
@require_auth
def distributor_team():
    code = request.dist_code
    conn = get_conn()

    def get_subtree(parent, depth, max_depth=4):
        if depth > max_depth:
            return []
        recruits = conn.execute(
            "SELECT d.* FROM distributors d JOIN recruits r ON d.code=r.recruit_code WHERE r.sponsor_code=?",
            (parent,)
        ).fetchall()
        result = []
        for r in recruits:
            d = dict(r)
            ms = get_maintenance_status(d, conn)
            node = {
                "code":   d["code"],
                "name":   f"{d['fname']} {d['lname']}",
                "rank":   ms["rank"]["name"],
                "status": ms["status"],
                "level":  depth,
                "children": get_subtree(d["code"], depth+1, max_depth)
            }
            result.append(node)
        return result

    tree = get_subtree(code, 1)
    conn.close()
    return jsonify({"tree": tree})


@api.route("/distributor/payouts", methods=["GET","POST"])
@require_auth
def distributor_payouts():
    code = request.dist_code
    conn = get_conn()
    if request.method == "POST":
        data = request.get_json(force=True)
        amount = int(data.get("amount", 0))
        # Check available balance
        avail = conn.execute(
            "SELECT COALESCE(SUM(commission),0) as total FROM commissions WHERE beneficiary=? AND status='available'",
            (code,)
        ).fetchone()["total"]
        if amount <= 0 or amount > avail:
            conn.close()
            return jsonify({"error": f"Insufficient balance. Available: R{avail}"}), 400
        conn.execute("""
            INSERT INTO payouts(dist_code,amount,bank_name,account_name,account_no,branch_code)
            VALUES(?,?,?,?,?,?)
        """, (code, amount, data.get("bank",""), data.get("account_name",""),
              data.get("account_no",""), data.get("branch_code","")))
        # Reserve the commissions
        conn.execute("""
            UPDATE commissions SET status='pending'
            WHERE beneficiary=? AND status='available'
            LIMIT (SELECT COUNT(*) FROM commissions WHERE beneficiary=? AND status='available')
        """, (code, code))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Payout request submitted."})

    rows = conn.execute(
        "SELECT * FROM payouts WHERE dist_code=? ORDER BY requested_at DESC", (code,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ──────────────────────────────────────────────────────────
# MAINTENANCE
# ──────────────────────────────────────────────────────────
@api.route("/distributor/maintenance", methods=["GET"])
@require_auth
def get_maintenance():
    code = request.dist_code
    conn = get_conn()
    row = conn.execute("SELECT * FROM distributors WHERE code=?", (code,)).fetchone()
    ms = get_maintenance_status(dict(row), conn)
    history = conn.execute(
        "SELECT * FROM maintenance_payments WHERE dist_code=? ORDER BY created_at DESC", (code,)
    ).fetchall()
    conn.close()
    return jsonify({
        "status": ms,
        "history": [dict(r) for r in history]
    })


@api.route("/distributor/maintenance/pay", methods=["POST"])
@require_auth
def pay_maintenance():
    """Submit a maintenance payment (records as pending until admin confirms)."""
    code = request.dist_code
    data = request.get_json(force=True)
    conn = get_conn()
    row = conn.execute("SELECT * FROM distributors WHERE code=?", (code,)).fetchone()
    ms = get_maintenance_status(dict(row), conn)

    order_no = f"MAINT-{code}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    conn.execute("""
        INSERT INTO maintenance_payments(dist_code,amount,method,status,order_ref,created_at)
        VALUES(?,?,?,?,?,?)
    """, (code, ms["fee"], data.get("method","card"), "pending",
          order_no, datetime.utcnow().isoformat()))

    # Also create an order record so it goes through checkout
    conn.execute("""
        INSERT INTO orders
        (order_no,customer_name,customer_phone,customer_email,pep_store,
         product,qty,unit_price,subtotal,shipping,total,
         payment_method,payment_status,order_type,dist_code)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        order_no,
        f"{row['fname']} {row['lname']}",
        row["phone"], row["email"],
        "N/A",
        f"Monthly Maintenance Fee ({ms['rank']['name']})",
        1, ms["fee"], ms["fee"], 0, ms["fee"],
        data.get("method","card"), "pending", "maintenance", code
    ))
    conn.commit()
    conn.close()
    return jsonify({
        "success":  True,
        "order_no": order_no,
        "amount":   ms["fee"],
        "message":  "Maintenance payment initiated. Proceed to checkout."
    })


# ──────────────────────────────────────────────────────────
# ORDERS / CHECKOUT
# ──────────────────────────────────────────────────────────
@api.route("/orders", methods=["POST"])
def create_order():
    """Public order endpoint — products + registration packs."""
    data = request.get_json(force=True)
    required = ["customer_name","customer_phone","customer_email","pep_store","product","qty"]
    for f in required:
        if not str(data.get(f,"")).strip():
            return jsonify({"error": f"Field '{f}' is required."}), 400

    qty = int(data.get("qty", 1))
    order_no = f"SN{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4())[:4].upper()}"
    subtotal = qty * PRODUCT_PRICE
    total    = subtotal + SHIPPING_FEE

    conn = get_conn()
    conn.execute("""
        INSERT INTO orders
        (order_no,customer_name,customer_phone,customer_email,pep_store,
         product,qty,unit_price,subtotal,shipping,total,
         referral_code,payment_method,payment_status,order_type,dist_code)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        order_no, data["customer_name"].strip(), data["customer_phone"].strip(),
        data["customer_email"].strip().lower(), data["pep_store"].strip(),
        data["product"], qty, PRODUCT_PRICE, subtotal, SHIPPING_FEE, total,
        data.get("referral_code","") or None,
        data.get("payment_method","card"), "pending", "product",
        data.get("dist_code") or None
    ))
    conn.commit()
    conn.close()
    return jsonify({
        "success":  True,
        "order_no": order_no,
        "subtotal": subtotal,
        "shipping": SHIPPING_FEE,
        "total":    total,
    }), 201


@api.route("/orders/<order_no>/confirm-payment", methods=["POST"])
def confirm_order_payment(order_no):
    """Mark an order as paid (call from front-end after payment succeeds)."""
    data = request.get_json(force=True)
    conn = get_conn()
    order = conn.execute(
        "SELECT * FROM orders WHERE order_no=?", (order_no,)
    ).fetchone()
    if not order:
        conn.close()
        return jsonify({"error": "Order not found"}), 404

    conn.execute("""
        UPDATE orders SET payment_status='paid', payment_method=?, paid_at=?
        WHERE order_no=?
    """, (data.get("method","card"), datetime.utcnow().isoformat(), order_no))

    # If it was a product order, create a sales record if dist_code present
    if order["order_type"] == "product" and order["dist_code"]:
        conn.execute(
            "INSERT INTO sales(dist_code,order_no,product,qty,amount) VALUES(?,?,?,?,?)",
            (order["dist_code"], order_no, order["product"],
             order["qty"], order["subtotal"])
        )
        commissions = compute_commissions(order["subtotal"], order["dist_code"], conn)
        for c in commissions:
            conn.execute("""
                INSERT INTO commissions(beneficiary,source_code,level,rate,sale_amount,commission,order_no,status)
                VALUES(?,?,?,?,?,?,?,'available')
            """, (c["beneficiary"], c["source_code"], c["level"],
                  c["rate"], c["sale_amount"], c["commission"], order_no))

    # If registration, activate distributor
    if order["order_type"] == "registration" and order["dist_code"]:
        conn.execute(
            "UPDATE distributors SET status='active' WHERE code=?",
            (order["dist_code"],)
        )

    # If maintenance, confirm the payment record
    if order["order_type"] == "maintenance" and order["dist_code"]:
        conn.execute("""
            UPDATE maintenance_payments SET status='confirmed', paid_at=?, confirmed_at=?
            WHERE order_ref=? AND status='pending'
        """, (datetime.utcnow().strftime("%Y-%m-%d"),
              datetime.utcnow().isoformat(), order_no))
        conn.execute(
            "UPDATE distributors SET status='active', status_override=NULL WHERE code=?",
            (order["dist_code"],)
        )

    conn.commit()
    conn.close()
    return jsonify({"success": True, "order_no": order_no, "status": "paid"})


@api.route("/orders/<order_no>", methods=["GET"])
def get_order(order_no):
    conn = get_conn()
    row = conn.execute("SELECT * FROM orders WHERE order_no=?", (order_no,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(dict(row))


# ──────────────────────────────────────────────────────────
# ADMIN
# ──────────────────────────────────────────────────────────
@api.route("/admin/distributors", methods=["GET"])
@require_admin
def admin_distributors():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM distributors ORDER BY join_date DESC").fetchall()
    result = []
    for row in rows:
        d = dict(row)
        ms = get_maintenance_status(d, conn)
        rc = conn.execute(
            "SELECT COUNT(*) as cnt FROM recruits WHERE sponsor_code=?", (d["code"],)
        ).fetchone()["cnt"]
        sales = conn.execute(
            "SELECT COALESCE(SUM(qty),0) as units FROM sales WHERE dist_code=?", (d["code"],)
        ).fetchone()["units"]
        result.append({
            **d,
            "password_hash": "***",
            "rank":          ms["rank"]["name"],
            "maintenance":   ms,
            "direct_recruits": rc,
            "units_sold":    sales,
        })
    conn.close()
    return jsonify(result)


@api.route("/admin/distributors/<code>/suspend", methods=["POST"])
@require_admin
def admin_suspend(code):
    data = request.get_json(force=True) or {}
    conn = get_conn()
    row = conn.execute("SELECT * FROM distributors WHERE code=?", (code,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    ms = get_maintenance_status(dict(row), conn)
    # Enforce grace period unless force=True
    if ms["days_overdue"] <= 7 and not data.get("force"):
        conn.close()
        return jsonify({
            "error": f"Grace period active — {7-ms['days_overdue']} days remaining. Use force=true to override."
        }), 400
    conn.execute(
        "UPDATE distributors SET status_override='suspended' WHERE code=?", (code,)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "code": code, "status": "suspended"})


@api.route("/admin/distributors/<code>/activate", methods=["POST"])
@require_admin
def admin_activate(code):
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM distributors WHERE code=?", (code,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    conn.execute(
        "UPDATE distributors SET status='active', status_override='active' WHERE code=?", (code,)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "code": code, "status": "active"})


@api.route("/admin/maintenance", methods=["GET"])
@require_admin
def admin_maintenance():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM distributors ORDER BY fname").fetchall()
    result = []
    for row in rows:
        d = dict(row)
        ms = get_maintenance_status(d, conn)
        pending = conn.execute(
            "SELECT COUNT(*) as cnt FROM maintenance_payments WHERE dist_code=? AND status='pending'",
            (d["code"],)
        ).fetchone()["cnt"]
        result.append({
            "code":        d["code"],
            "name":        f"{d['fname']} {d['lname']}",
            "rank":        ms["rank"]["name"],
            "fee":         ms["fee"],
            "status":      ms["status"],
            "days_overdue": ms["days_overdue"],
            "next_due":    ms["next_due"],
            "last_paid":   ms["last_paid"],
            "pending_payments": pending,
        })
    conn.close()
    return jsonify(result)


@api.route("/admin/maintenance/<code>/confirm", methods=["POST"])
@require_admin
def admin_confirm_maintenance(code):
    conn = get_conn()
    mp = conn.execute(
        "SELECT * FROM maintenance_payments WHERE dist_code=? AND status='pending' ORDER BY created_at LIMIT 1",
        (code,)
    ).fetchone()
    if not mp:
        conn.close()
        return jsonify({"error": "No pending maintenance payment."}), 404
    now = datetime.utcnow().isoformat()
    conn.execute("""
        UPDATE maintenance_payments
        SET status='confirmed', paid_at=?, confirmed_at=?
        WHERE id=?
    """, (datetime.utcnow().strftime("%Y-%m-%d"), now, mp["id"]))
    conn.execute(
        "UPDATE distributors SET status='active', status_override=NULL WHERE code=?", (code,)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@api.route("/admin/payouts", methods=["GET"])
@require_admin
def admin_payouts():
    conn = get_conn()
    rows = conn.execute("""
        SELECT p.*, d.fname, d.lname, d.email, d.phone
        FROM payouts p JOIN distributors d ON p.dist_code=d.code
        ORDER BY p.requested_at DESC
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@api.route("/admin/payouts/<int:payout_id>/approve", methods=["POST"])
@require_admin
def admin_approve_payout(payout_id):
    conn = get_conn()
    payout = conn.execute("SELECT * FROM payouts WHERE id=?", (payout_id,)).fetchone()
    if not payout or payout["status"] != "pending":
        conn.close()
        return jsonify({"error": "Not found or already processed"}), 404
    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE payouts SET status='approved', processed_at=? WHERE id=?", (now, payout_id)
    )
    # Mark commissions as paid
    conn.execute("""
        UPDATE commissions SET status='paid'
        WHERE beneficiary=? AND status='pending'
    """, (payout["dist_code"],))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@api.route("/admin/payouts/<int:payout_id>/reject", methods=["POST"])
@require_admin
def admin_reject_payout(payout_id):
    conn = get_conn()
    conn.execute(
        "UPDATE payouts SET status='rejected', processed_at=? WHERE id=?",
        (datetime.utcnow().isoformat(), payout_id)
    )
    # Restore commissions to available
    payout = conn.execute("SELECT * FROM payouts WHERE id=?", (payout_id,)).fetchone()
    if payout:
        conn.execute("""
            UPDATE commissions SET status='available'
            WHERE beneficiary=? AND status='pending'
        """, (payout["dist_code"],))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@api.route("/admin/orders", methods=["GET"])
@require_admin
def admin_orders():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM orders ORDER BY created_at DESC LIMIT 200"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@api.route("/admin/stats", methods=["GET"])
@require_admin
def admin_stats():
    conn = get_conn()
    total_dist    = conn.execute("SELECT COUNT(*) as n FROM distributors").fetchone()["n"]
    active_dist   = conn.execute("SELECT COUNT(*) as n FROM distributors WHERE status='active'").fetchone()["n"]
    total_rev     = conn.execute("SELECT COALESCE(SUM(total),0) as t FROM orders WHERE payment_status='paid'").fetchone()["t"]
    total_units   = conn.execute("SELECT COALESCE(SUM(qty),0) as t FROM sales").fetchone()["t"]
    pending_payouts = conn.execute("SELECT COUNT(*) as n FROM payouts WHERE status='pending'").fetchone()["n"]
    conn.close()
    return jsonify({
        "total_distributors": total_dist,
        "active_distributors": active_dist,
        "total_revenue":      total_rev,
        "total_units_sold":   total_units,
        "pending_payouts":    pending_payouts,
    })


# ──────────────────────────────────────────────────────────
# PUBLIC
# ──────────────────────────────────────────────────────────
@api.route("/referral/<code>", methods=["GET"])
def check_referral(code):
    conn = get_conn()
    row = conn.execute(
        "SELECT fname, lname, city FROM distributors WHERE code=?",
        (code.upper(),)
    ).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Referral code not found"}), 404
    return jsonify({"name": f"{row['fname']} {row['lname']}", "city": row["city"]})


@api.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "app": "SiLu Naturals API", "version": "1.0.0"})
