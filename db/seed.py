"""
SiLu Naturals — seed demo data into the SQLite database.
Run once after init_db().
"""
import hashlib, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db.schema import get_conn, init_db

RANKS = [
    {"name": "Member",      "min_ref": 5,   "rate": 0.10, "levels": 1, "maintenance": 600},
    {"name": "Team Player", "min_ref": 10,  "rate": 0.10, "levels": 3, "maintenance": 600},
    {"name": "Team Leader", "min_ref": 30,  "rate": 0.12, "levels": 3, "maintenance": 800},
    {"name": "Manager",     "min_ref": 100, "rate": 0.14, "levels": 3, "maintenance": 800},
    {"name": "Director",    "min_ref": 500, "rate": 0.16, "levels": 3, "maintenance": 1000},
    {"name": "Chairperson", "min_ref": 800, "rate": 0.18, "levels": 4, "maintenance": 1000},
]

def pw(plain): return hashlib.sha256(plain.encode()).hexdigest()

DEMO_DISTRIBUTORS = [
    {"code":"THANDI001","fname":"Thandi","lname":"Dlamini","email":"thandi@demo.com",
     "phone":"0821234567","id_number":"8501015009087","city":"Port Elizabeth",
     "pack":"Gold","sponsor_code":None,"join_date":"2026-01-15","rank_name":"Manager",
     "status":"active"},
    {"code":"SIPHO002","fname":"Sipho","lname":"Nkosi","email":"sipho@demo.com",
     "phone":"0832345678","id_number":"9001015009087","city":"Johannesburg",
     "pack":"Silver","sponsor_code":"THANDI001","join_date":"2026-02-10","rank_name":"Team Player",
     "status":"active"},
    {"code":"LERATO003","fname":"Lerato","lname":"Mokoena","email":"lerato@demo.com",
     "phone":"0843456789","id_number":"9201015009087","city":"Cape Town",
     "pack":"Platinum","sponsor_code":"THANDI001","join_date":"2026-02-14","rank_name":"Team Player",
     "status":"active"},
    {"code":"ZANELE004","fname":"Zanele","lname":"Zulu","email":"zanele@demo.com",
     "phone":"0614567890","id_number":"8801015009087","city":"Durban",
     "pack":"Silver","sponsor_code":"SIPHO002","join_date":"2026-03-01","rank_name":"Member",
     "status":"grace"},
    {"code":"BONGANI005","fname":"Bongani","lname":"Khumalo","email":"bongani@demo.com",
     "phone":"0625678901","id_number":"9501015009087","city":"Pretoria",
     "pack":"Silver","sponsor_code":"SIPHO002","join_date":"2026-02-20","rank_name":"Member",
     "status":"active"},
    {"code":"NOMSA006","fname":"Nomsa","lname":"Sithole","email":"nomsa@demo.com",
     "phone":"0716789012","id_number":"0001015009087","city":"East London",
     "pack":"Silver","sponsor_code":"LERATO003","join_date":"2026-02-25","rank_name":"Member",
     "status":"active"},
    {"code":"KHOSI007","fname":"Khosi","lname":"Mahlangu","email":"khosi@demo.com",
     "phone":"0727890123","id_number":"9701015009087","city":"Nelspruit",
     "pack":"Gold","sponsor_code":"LERATO003","join_date":"2026-03-05","rank_name":"Member",
     "status":"active"},
    {"code":"TEBOGO008","fname":"Tebogo","lname":"Molefe","email":"tebogo@demo.com",
     "phone":"0838901234","id_number":"0101015009087","city":"Bloemfontein",
     "pack":"Silver","sponsor_code":"LERATO003","join_date":"2026-03-08","rank_name":"Member",
     "status":"suspended"},
    {"code":"AYANDA009","fname":"Ayanda","lname":"Mthembu","email":"ayanda@demo.com",
     "phone":"0849012345","id_number":"9901015009087","city":"Pietermaritzburg",
     "pack":"Silver","sponsor_code":"THANDI001","join_date":"2026-03-10","rank_name":"Member",
     "status":"active"},
]

RECRUITS = [
    ("THANDI001","SIPHO002"),("THANDI001","LERATO003"),("THANDI001","AYANDA009"),
    ("SIPHO002","ZANELE004"),("SIPHO002","BONGANI005"),
    ("LERATO003","NOMSA006"),("LERATO003","KHOSI007"),("LERATO003","TEBOGO008"),
]

def seed():
    init_db()
    conn = get_conn()
    c = conn.cursor()

    # Clear for idempotency
    c.execute("DELETE FROM recruits")
    c.execute("DELETE FROM distributors")
    c.execute("DELETE FROM admins")
    c.execute("DELETE FROM maintenance_payments")
    c.execute("DELETE FROM sales")
    c.execute("DELETE FROM commissions")

    # Insert demo distributors
    for d in DEMO_DISTRIBUTORS:
        c.execute("""INSERT OR REPLACE INTO distributors
            (code,fname,lname,email,phone,id_number,city,pack,sponsor_code,
             password_hash,status,join_date,rank_name)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d["code"],d["fname"],d["lname"],d["email"],d["phone"],d["id_number"],
             d["city"],d["pack"],d["sponsor_code"],pw("demo1234"),
             d["status"],d["join_date"],d["rank_name"]))

    # Insert recruits
    for sponsor, recruit in RECRUITS:
        c.execute("INSERT OR IGNORE INTO recruits(sponsor_code,recruit_code) VALUES(?,?)",
                  (sponsor, recruit))

    # Insert admin
    c.execute("""INSERT OR REPLACE INTO admins(username,password_hash)
                 VALUES('admin', ?)""", (pw("admin123"),))

    # Seed some maintenance payments
    c.execute("""INSERT INTO maintenance_payments(dist_code,amount,status,method,paid_at,created_at)
                 VALUES('THANDI001',800,'confirmed','card','2026-03-15','2026-03-15')""")
    c.execute("""INSERT INTO maintenance_payments(dist_code,amount,status,method,paid_at,created_at)
                 VALUES('SIPHO002',600,'confirmed','card','2026-03-20','2026-03-20')""")
    c.execute("""INSERT INTO maintenance_payments(dist_code,amount,status,method,created_at)
                 VALUES('ZANELE004',600,'pending','card','2026-04-20')""")

    # Seed some sales
    sales_data = [
        ("THANDI001","Hair Growth Oil",3,600),
        ("THANDI001","Hair Growth Serum",2,400),
        ("SIPHO002","Hair Growth Oil",1,200),
        ("LERATO003","Hair Growth Serum",2,400),
        ("BONGANI005","Hair Growth Oil",1,200),
    ]
    for code, product, qty, amount in sales_data:
        c.execute("""INSERT INTO sales(dist_code,product,qty,amount)
                     VALUES(?,?,?,?)""", (code,product,qty,amount))

    conn.commit()
    conn.close()
    print("[SEED] Demo data seeded ✓")

if __name__ == "__main__":
    seed()
