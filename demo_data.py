"""
SN Gym Management System - optional demo data
Developed by SN Softech Solutions

Loads a realistic sample gym (members, trainers, sales, attendance, expenses)
so a new install can be demonstrated immediately. It only ever ADDS rows -
existing records are never touched or overwritten.
"""

import random
from datetime import date, timedelta

import database as db

FIRST = ["Ramesh", "Priya", "Arjun", "Sneha", "Vikram", "Anita", "Rahul", "Meera", "Karan",
         "Divya", "Sanjay", "Pooja", "Amit", "Nisha", "Rohit", "Kavya", "Manish", "Farah",
         "Imran", "Deepa", "Suresh", "Anjali", "Nikhil", "Tara"]
LAST = ["Sharma", "Patel", "Nair", "Reddy", "Singh", "Iyer", "Khan", "Verma", "Gupta", "Menon"]
GOALS = ["Weight Loss", "Muscle Gain", "General Fitness", "Strength", "Endurance"]
TRAINERS = [("Vijay Kumar", "Strength & Conditioning"), ("Neha Joshi", "Weight Loss"),
            ("Sameer Ali", "Bodybuilding"), ("Ritu Das", "Yoga")]


def already_loaded(gym_id):
    return bool(db.fetch_value(
        "SELECT COUNT(*) FROM members WHERE gym_id=? AND medical_notes='DEMO'", (gym_id,)))


def clear_demo(gym_id):
    """Remove only the demo rows, leaving real data alone."""
    ids = [r["id"] for r in db.fetch_all(
        "SELECT id FROM members WHERE gym_id=? AND medical_notes='DEMO'", (gym_id,))]
    for member_id in ids:
        db.execute("DELETE FROM members WHERE id=?", (member_id,))
    db.execute("DELETE FROM trainers WHERE gym_id=? AND email LIKE '%@demo.gym'", (gym_id,))
    db.execute("DELETE FROM expenses WHERE gym_id=? AND notes='DEMO'", (gym_id,))
    db.execute("DELETE FROM products WHERE gym_id=? AND supplier='DEMO Supplies'", (gym_id,))
    return len(ids)


def load(gym_id, member_count=24):
    """Create the sample gym. Returns a short summary string."""
    random.seed(7)
    today = date.today()

    trainer_ids = []
    for name, spec in TRAINERS:
        trainer_ids.append(db.execute(
            """INSERT INTO trainers (gym_id, trainer_name, mobile, email, specialization,
                   joining_date, salary, commission, status)
               VALUES (?,?,?,?,?,?,?,?, 'Active')""",
            (gym_id, name, f"98{random.randint(10000000, 99999999)}",
             name.split()[0].lower() + "@demo.gym", spec,
             (today - timedelta(days=random.randint(200, 900))).strftime("%Y-%m-%d"),
             random.choice([18000, 22000, 25000, 30000]), random.choice([5, 8, 10]))))

    db.seed_plans(gym_id)
    plans = db.fetch_all("SELECT * FROM membership_plans WHERE gym_id=?", (gym_id,))
    start_code = db.fetch_value("SELECT COUNT(*) FROM members WHERE gym_id=?", (gym_id,))

    member_ids = []
    for i in range(member_count):
        name = f"{random.choice(FIRST)} {random.choice(LAST)}"
        joined = today - timedelta(days=random.randint(5, 420))
        code = f"M{start_code + i + 1:04d}"
        member_id = db.execute(
            """INSERT INTO members (gym_id, member_code, full_name, gender, dob, mobile, whatsapp,
                   email, address, emergency_contact, joining_date, blood_group, height, weight,
                   fitness_goal, medical_notes, trainer_id, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'DEMO',?, 'Active')""",
            (gym_id, code, name, random.choice(["Male", "Female"]),
             f"{random.randint(1975, 2004)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
             f"9{random.randint(100000000, 999999999)}", "",
             name.split()[0].lower() + str(i) + "@example.com", "Demo address, City",
             f"9{random.randint(100000000, 999999999)}", joined.strftime("%Y-%m-%d"),
             random.choice(["A+", "B+", "O+", "AB+"]), random.randint(150, 190),
             random.randint(52, 105), random.choice(GOALS), random.choice(trainer_ids)))
        member_ids.append(member_id)

        # 1 to 3 memberships each, so renewals and expiries both appear
        anchor = joined
        for seq in range(random.randint(1, 3)):
            plan = random.choice(plans)
            months = int(plan["duration_months"]) or 1
            end = anchor + timedelta(days=int(months * 30))
            amount = float(plan["price"])
            discount = round(amount * float(plan["discount"] or 0) / 100, 2)
            net = amount - discount
            paid = net if random.random() > 0.25 else round(net * random.choice([0.4, 0.6, 0.8]), 2)
            due = round(net - paid, 2)
            invoice = f"INV-DEMO-{member_id:04d}{seq}"
            ms_id = db.execute(
                """INSERT INTO memberships (gym_id, member_id, plan_id, plan_name, sale_type,
                       invoice_no, start_date, end_date, amount, discount, net_amount, paid_amount,
                       due_amount, payment_mode, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (gym_id, member_id, plan["id"], plan["plan_name"],
                 "New" if seq == 0 else "Renewal", invoice, anchor.strftime("%Y-%m-%d"),
                 end.strftime("%Y-%m-%d"), amount, discount, net, paid, due,
                 random.choice(db.PAYMENT_MODES), anchor.strftime("%Y-%m-%d %H:%M:%S")))
            db.execute(
                """INSERT INTO payments (gym_id, member_id, invoice_no, pay_date, category,
                       ref_table, ref_id, amount, paid_amount, due_amount, payment_mode, status)
                   VALUES (?,?,?,?,?, 'memberships',?,?,?,?,?,?)""",
                (gym_id, member_id, invoice, anchor.strftime("%Y-%m-%d"),
                 "Membership" if seq == 0 else "Renewal", ms_id, net, paid, due,
                 random.choice(db.PAYMENT_MODES), "Paid" if due == 0 else "Partial"))
            anchor = end + timedelta(days=1)

    # Attendance for the last 45 days
    for day_offset in range(45):
        day = today - timedelta(days=day_offset)
        for member_id in random.sample(member_ids, k=max(3, int(len(member_ids) * 0.45))):
            try:
                db.execute("""INSERT OR IGNORE INTO attendance (gym_id, member_id, att_date,
                              check_in, check_out, status) VALUES (?,?,?,?,?,'Present')""",
                           (gym_id, member_id, day.strftime("%Y-%m-%d"),
                            f"{random.randint(6, 20):02d}:{random.choice(['00', '15', '30', '45'])}",
                            f"{random.randint(7, 22):02d}:{random.choice(['00', '20', '40'])}"))
            except Exception:
                pass

    # Personal training packages
    for member_id in random.sample(member_ids, k=min(6, len(member_ids))):
        total = random.choice([8, 12, 16])
        amount = total * 500
        db.execute(
            """INSERT INTO personal_training (gym_id, member_id, trainer_id, package_name,
                   total_sessions, used_sessions, start_date, end_date, amount, paid_amount,
                   due_amount, invoice_no, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'Active')""",
            (gym_id, member_id, random.choice(trainer_ids), f"PT - {total} Sessions", total,
             random.randint(0, total - 1), (today - timedelta(days=20)).strftime("%Y-%m-%d"),
             (today + timedelta(days=40)).strftime("%Y-%m-%d"), amount, amount, 0,
             f"PT-DEMO-{member_id:04d}"))

    # Expenses for the last 5 months
    for month_offset in range(5):
        base = (today.replace(day=1) - timedelta(days=month_offset * 30))
        for category, amount in [("Rent", 45000), ("Electricity", 12000), ("Salary", 90000),
                                 ("Maintenance", 6000), ("Marketing", 8000), ("Cleaning", 4000)]:
            db.execute("""INSERT INTO expenses (gym_id, exp_date, category, description, amount,
                          payment_mode, notes) VALUES (?,?,?,?,?,?, 'DEMO')""",
                       (gym_id, base.strftime("%Y-%m-%d"), category, f"{category} for the month",
                        amount + random.randint(-1500, 1500), random.choice(db.PAYMENT_MODES)))

    # Products
    for name, category, purchase, selling, stock in [
            ("Whey Protein 1kg", "Supplement", 2200, 2999, 14),
            ("Creatine 250g", "Supplement", 900, 1350, 9),
            ("BCAA 300g", "Supplement", 1100, 1650, 4),
            ("Shaker Bottle", "Accessory", 120, 299, 25),
            ("Gym Gloves", "Accessory", 250, 599, 3),
            ("Energy Drink", "Beverage", 45, 90, 60)]:
        db.execute("""INSERT INTO products (gym_id, product_name, category, barcode, purchase_price,
                      selling_price, stock, low_stock_limit, supplier, status)
                      VALUES (?,?,?,?,?,?,?,?, 'DEMO Supplies', 'Active')""",
                   (gym_id, name, category, f"890{random.randint(1000000, 9999999)}",
                    purchase, selling, stock, 5))

    return (f"Loaded {member_count} members, {len(TRAINERS)} trainers, memberships, "
            f"45 days of attendance, PT packages, expenses and products.")
