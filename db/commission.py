"""
SiLu Naturals — commission engine
Calculates rank, maintenance fee, and multi-level commissions.
"""

RANKS = [
    {"name": "Unranked",    "min_ref": 0,   "rate": 0.00, "levels": 0, "maintenance": 0,    "bonus": 0},
    {"name": "Member",      "min_ref": 5,   "rate": 0.10, "levels": 1, "maintenance": 600,  "bonus": 0},
    {"name": "Team Player", "min_ref": 10,  "rate": 0.10, "levels": 3, "maintenance": 600,  "bonus": 1000},
    {"name": "Team Leader", "min_ref": 30,  "rate": 0.12, "levels": 3, "maintenance": 800,  "bonus": 1500},
    {"name": "Manager",     "min_ref": 100, "rate": 0.14, "levels": 3, "maintenance": 800,  "bonus": 2000},
    {"name": "Director",    "min_ref": 500, "rate": 0.16, "levels": 3, "maintenance": 1000, "bonus": 5000},
    {"name": "Chairperson", "min_ref": 800, "rate": 0.18, "levels": 4, "maintenance": 1000, "bonus": 10000},
]

PACK_PRICES = {"Silver": 600, "Gold": 800, "Platinum": 1000}
PACK_CONTENTS = {
    "Silver":   "3× Hair Growth Oil + 3× Hair Growth Serum",
    "Gold":     "4× Hair Growth Oil + 4× Hair Growth Serum",
    "Platinum": "5× Hair Growth Oil + 5× Hair Growth Serum",
}
PRODUCT_PRICE = 200
SHIPPING_FEE  = 60


def get_rank(direct_recruits: int) -> dict:
    rank = RANKS[0]
    for r in RANKS:
        if direct_recruits >= r["min_ref"]:
            rank = r
    return rank


def get_maintenance_status(dist: dict, conn) -> dict:
    """
    Returns maintenance status dict:
      { status, days_overdue, next_due, last_paid, fee }
    """
    import sqlite3
    from datetime import datetime, timedelta

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Count direct recruits
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM recruits WHERE sponsor_code=?",
        (dist["code"],)
    ).fetchone()
    direct = row["cnt"] if row else 0
    rank = get_rank(direct)
    fee = rank["maintenance"]

    # Manual override?
    override = dist["status_override"]

    # Last confirmed maintenance payment
    paid_row = conn.execute("""
        SELECT paid_at FROM maintenance_payments
        WHERE dist_code=? AND status='confirmed'
        ORDER BY paid_at DESC LIMIT 1
    """, (dist["code"],)).fetchone()

    if paid_row and paid_row["paid_at"]:
        last_paid = datetime.fromisoformat(paid_row["paid_at"][:10])
    else:
        last_paid = datetime.fromisoformat(dist["join_date"][:10])

    next_due = last_paid + timedelta(days=30)
    days_overdue = (today - next_due).days

    if override == "suspended":
        status = "suspended"
    elif override == "active":
        status = "active"
    elif days_overdue <= 0:
        status = "active"
    elif days_overdue <= 7:
        status = "grace"
    else:
        status = "suspended"

    return {
        "status":       status,
        "days_overdue": days_overdue,
        "next_due":     next_due.strftime("%Y-%m-%d"),
        "last_paid":    last_paid.strftime("%Y-%m-%d"),
        "fee":          fee,
        "rank":         rank,
        "direct":       direct,
    }


def compute_commissions(sale_amount: int, seller_code: str, conn) -> list:
    """
    Walk up the sponsor chain and calculate commissions for each level.
    Returns list of {"beneficiary", "level", "rate", "commission", "source_code"}
    """
    results = []
    current = seller_code
    visited = set()

    for level in range(1, 5):  # max 4 levels (Chairperson)
        row = conn.execute(
            "SELECT * FROM distributors WHERE code=?", (current,)
        ).fetchone()
        if not row:
            break
        sponsor_code = row["sponsor_code"]
        if not sponsor_code or sponsor_code in visited:
            break
        visited.add(sponsor_code)

        sponsor = conn.execute(
            "SELECT * FROM distributors WHERE code=?", (sponsor_code,)
        ).fetchone()
        if not sponsor:
            break

        # Check sponsor is active
        ms = get_maintenance_status(dict(sponsor), conn)
        if ms["status"] != "active":
            current = sponsor_code
            continue

        rank = ms["rank"]
        if level > rank["levels"]:
            current = sponsor_code
            continue

        comm_amount = int(sale_amount * rank["rate"])
        results.append({
            "beneficiary": sponsor_code,
            "source_code": seller_code,
            "level":       level,
            "rate":        rank["rate"],
            "commission":  comm_amount,
            "sale_amount": sale_amount,
        })
        current = sponsor_code

    return results
