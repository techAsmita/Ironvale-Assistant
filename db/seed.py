"""Seed the Ironvale plant database: 1 Aug to 31 Oct 2026, 10 machines, ~1,500 work orders,
~2,000 downtime events, defects and supplier prices. Deterministic (seed 3).

    python db/seed.py            # uses DATABASE_URL from .env

The seed agrees with the planted facts: Arcflow Castings supplies HX-220-B at Rs 412 (F8), cracked
HX-220-B housings were found on CNC-L1-04 in September 2026 (F6, QDR-2026-014), and E-417 is a
coolant-pressure breakdown on the DMC 850 machines (F1).
"""
from __future__ import annotations

import os
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
rng = random.Random(3)

USERS = [
    ("u_sup_l1", "Priya Natarajan", "line_supervisor", 1),
    ("u_sup_l3", "Karthik Selvam", "line_supervisor", 3),
    ("u_qe", "Farah Qureshi", "quality_engineer", None),
    ("u_head", "Vikram Rao", "plant_head", None),
]

MACHINES = (
    [(f"CNC-L1-0{i}", 1, "CNC machining centre", "DMC 850", date(2019 + i % 4, 1 + i, 10)) for i in range(1, 7)]
    + [("FUR-L2-01", 2, "Batch furnace", "Thermex BF-600", date(2018, 6, 1)),
       ("FUR-L2-02", 2, "Batch furnace", "Thermex BF-600", date(2021, 3, 15)),
       ("PRS-L3-01", 3, "Servo press", "Kompress SP-30", date(2020, 9, 1)),
       ("LKT-L3-01", 3, "Leak tester", "AirCheck LT-2", date(2022, 2, 1))]
)

PARTS = {  # machine -> parts it runs, with weights
    1: [("HX-220-B", 0.65), ("BR-310-A", 0.35)],
    2: [("HX-220-B", 0.6), ("BR-310-A", 0.4)],
    3: [("HX-220-B", 1.0)],
}

SUPPLIER_PARTS = [
    ("HX-220-B", "Arcflow Castings", 412.00, date(2026, 7, 1)),
    ("BR-310-A", "Vellore Forge Works", 138.00, date(2026, 7, 1)),
    ("M8-FB", "Metsun Fasteners", 6.00, date(2026, 7, 1)),
    ("M6-CB", "Metsun Fasteners", 3.00, date(2026, 7, 1)),
]

ALARMS = {
    "CNC": [("E-417", 0.30), ("E-471", 0.18), ("E-402", 0.14), ("E-438", 0.16), ("E-490", 0.12), ("E-420", 0.10)],
    "FUR": [("F-30", 0.5), ("F-44", 0.2), ("F-12", 0.3)],
    "PRS": [("P-07", 0.6), ("P-12", 0.4)],
    "LKT": [("L-05", 0.6), ("L-11", 0.4)],
}
REASONS = {
    "planned": ["PM-WEEKLY", "PM-MONTHLY", "CLEANING", "TRIAL"],
    "changeover": ["CO-STD", "CO-LONG"],
    "material": ["MAT-SHORT", "MAT-QUALITY", "MAT-WAIT-HT"],
}

START, END = datetime(2026, 8, 1), datetime(2026, 11, 1)


def pick(weighted):
    r, acc = rng.random(), 0.0
    for v, w in weighted:
        acc += w
        if r <= acc:
            return v
    return weighted[-1][0]


def rand_time(day: date, h0=6, h1=22) -> datetime:
    return datetime(day.year, day.month, day.day, rng.randint(h0, h1 - 1), rng.randint(0, 59))


def build():
    days = [(START + timedelta(d)).date() for d in range((END - START).days)]
    work_orders, downtime, defects = [], [], []

    wo_n = 0
    for mid, line, mtype, *_ in MACHINES:
        per_day = {1: 1.65, 2: 1.5, 3: 1.7}[line]
        for day in days:
            n = int(per_day) + (1 if rng.random() < per_day % 1 else 0)
            for _ in range(n):
                wo_n += 1
                part = pick(PARTS[line])
                planned = rng.choice([120, 150, 200, 240, 300]) if line != 2 else rng.choice([400, 480, 600])
                yield_ = rng.uniform(0.93, 0.995)
                started = rand_time(day, 6, 18)
                work_orders.append((f"WO-{wo_n:05d}", mid, part, planned, int(planned * yield_),
                                    started, started + timedelta(hours=rng.uniform(3, 8))))

    ev = 0
    for mid, line, mtype, *_ in MACHINES:
        kind = mid.split("-")[0]
        per_day = {"CNC": 2.55, "FUR": 1.5, "PRS": 1.8, "LKT": 1.7}[kind]
        for day in days:
            n = int(per_day) + (1 if rng.random() < per_day % 1 else 0)
            for _ in range(n):
                ev += 1
                cat = pick([("breakdown", 0.42), ("changeover", 0.28), ("planned", 0.15), ("material", 0.15)])
                start = rand_time(day, 0, 24)
                if cat == "breakdown":
                    alarm = pick(ALARMS[kind])
                    # Coolant trouble on CNC-L1-04 in September (clogged filters from casting sand)
                    if mid == "CNC-L1-04" and day.month == 9 and rng.random() < 0.5:
                        alarm = "E-417"
                    minutes = rng.randint(10, 95)
                    reason = f"ALARM-{alarm}"
                elif cat == "changeover":
                    alarm, reason = None, rng.choice(REASONS["changeover"])
                    minutes = rng.randint(28, 48) if reason == "CO-STD" else rng.randint(51, 90)
                else:
                    alarm, reason = None, rng.choice(REASONS[cat])
                    minutes = rng.randint(15, 120)
                downtime.append((f"DT-{ev:05d}", mid, start, start + timedelta(minutes=minutes), cat, reason, alarm))

    # September: casting sand from the cracked Arcflow lot clogs the coolant filter on CNC-L1-04 -> extra E-417 stops
    for _ in range(26):
        ev += 1
        start = rand_time(date(2026, 9, rng.randint(1, 30)), 0, 24)
        downtime.append((f"DT-{ev:05d}", "CNC-L1-04", start, start + timedelta(minutes=rng.randint(20, 70)),
                         "breakdown", "ALARM-E-417", "E-417"))

    # Defects: a background rate plus the planted deviations
    by_machine_month: dict[tuple[str, int], list] = {}
    for wo in work_orders:
        by_machine_month.setdefault((wo[1], wo[5].month), []).append(wo)
    df = 0

    def add_defect(wo, dtype, qty, stage):
        nonlocal df
        df += 1
        defects.append((f"DF-{df:05d}", wo[0], wo[2], dtype, qty, wo[6] - timedelta(minutes=rng.randint(5, 90)), stage))

    background = {"CNC": [("bore oversize", "machining"), ("burr", "machining"), ("chatter marks", "machining")],
                  "FUR": [("distortion", "heat_treatment"), ("low hardness", "heat_treatment")],
                  "PRS": [("press-fit force out of window", "assembly")],
                  "LKT": [("leak", "final_test")]}
    for wo in work_orders:
        if rng.random() < 0.12:
            dtype, stage = rng.choice(background[wo[1].split("-")[0]])
            add_defect(wo, dtype, rng.randint(1, 4), stage)
    planted = [  # (machine, month, part, defect_type, stage, how many work orders, qty range)  -> QDRs
        ("PRS-L3-01", 8, "HX-220-B", "undersize thread M8 bolt", "assembly", 6, (3, 8)),    # QDR-2026-009 (Metsun)
        ("CNC-L1-02", 8, "HX-220-B", "porosity", "machining", 8, (4, 10)),                  # QDR-2026-012 (Arcflow)
        ("CNC-L1-04", 9, "HX-220-B", "crack", "machining", 12, (5, 14)),                    # QDR-2026-014 (Arcflow)
        ("FUR-L2-01", 9, "HX-220-B", "low hardness", "heat_treatment", 7, (6, 20)),         # QDR-2026-017
        ("LKT-L3-01", 10, "HX-220-B", "leak", "final_test", 9, (3, 9)),                     # QDR-2026-021
    ]
    for mid, month, part, dtype, stage, n, (lo, hi) in planted:
        pool = [w for w in by_machine_month[(mid, month)] if w[2] == part]
        for wo in rng.sample(pool, min(n, len(pool))):
            add_defect(wo, dtype, rng.randint(lo, hi), stage)

    return work_orders, downtime, defects


def main():
    sys.path.insert(0, str(ROOT / "backend"))
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("Set DATABASE_URL (see .env.example)")
    work_orders, downtime, defects = build()
    with psycopg.connect(url, autocommit=False) as conn, conn.cursor() as cur:
        cur.execute((ROOT / "db" / "schema.sql").read_text())
        cur.executemany("INSERT INTO users VALUES (%s,%s,%s,%s)", USERS)
        cur.executemany("INSERT INTO machines VALUES (%s,%s,%s,%s,%s)", MACHINES)
        cur.executemany("INSERT INTO supplier_parts VALUES (%s,%s,%s,%s)", SUPPLIER_PARTS)
        with cur.copy("COPY work_orders FROM STDIN") as cp:
            for r in work_orders:
                cp.write_row(r)
        with cur.copy("COPY downtime_events FROM STDIN") as cp:
            for r in downtime:
                cp.write_row(r)
        with cur.copy("COPY defects FROM STDIN") as cp:
            for r in defects:
                cp.write_row(r)
        cur.execute((ROOT / "db" / "security.sql").read_text())
        conn.commit()
    print(f"users {len(USERS)} · machines {len(MACHINES)} · work_orders {len(work_orders)} · "
          f"downtime_events {len(downtime)} · defects {len(defects)} · supplier_parts {len(SUPPLIER_PARTS)}")


if __name__ == "__main__":
    main()
