# SN Gym Management System

**Developed by SN Softech Solutions**

A commercial-grade gym and fitness centre management application: members, plans,
sales, renewals, attendance, trainers, personal training, collections, expenses,
stock, notifications, reports and KPI analytics — protected by a 1-year
licence-key activation system.

---

## 1. How to run the software

### Windows - the easy way (no commands)

1. Double-click **`INSTALL SETUP.bat`** — runs once, checks Python and installs
   everything into a private `venv` folder.
2. Double-click **`START GYM SOFTWARE.bat`** — the browser opens at
   `http://localhost:8501`. Keep the black window open while the gym is using it.
3. **`START ON NETWORK.bat`** does the same but prints the addresses a second PC
   or a tablet on the same WiFi can open.
4. **`TAKE BACKUP.bat`** saves a dated copy into `data\backups` and opens the folder.

Python 3.9+ must be installed first, with **"Add Python to PATH"** ticked
(https://python.org/downloads). The setup file says so if it is missing.
Right-click `START GYM SOFTWARE.bat` → *Send to* → *Desktop (create shortcut)*
to give the gym owner a one-click icon.

### Any operating system - the manual way

```bash
cd SN_Gym_Management
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`. On the first launch the database is
created automatically and the welcome / sign-up screen appears. After registering,
enter your licence key on the activation screen to unlock the software.

On any OS you can also serve it to the local network with
`streamlit run app.py --server.address 0.0.0.0 --server.port 8501`; other
machines then open `http://<this-computer-ip>:8501`.


## Using it on a mobile or tablet

The layout is responsive, so the same app works on a tablet and a phone — no
separate install is needed on those devices, they just open a web address.

1. On the gym's main computer, run **`START ON NETWORK.bat`**. It prints the
   address, for example `http://192.168.1.5:8501`.
2. Put the phone or tablet on the **same WiFi**, open Chrome or Safari and type
   that address.
3. Add it to the home screen (Chrome: *⋮ → Add to Home screen*, Safari:
   *Share → Add to Home Screen*) so it opens like an app, full screen.

Notes:

* The main computer must stay switched on with the black window open — it is the
  server; the phone is only a screen.
* The first time Windows may ask to allow Python through the firewall. Choose
  **Allow on private networks**, otherwise other devices cannot connect.
* On a phone the menu hides behind the **☰** button at the top left; on a tablet
  it stays open. Wide report tables scroll sideways with a finger.
* **Best fit by device:** tablet is comfortable for everything. A phone is ideal
  for attendance check-in, looking up a member, checking dues and the dashboard;
  long forms such as adding a new member and the wide reports are easier on the
  desktop or tablet.
* For access from outside the gym (owner checking KPIs from home) the app has to
  be hosted on a server or a cloud VM with HTTPS — the LAN address only works
  inside the gym's WiFi.

## 2. Required Python version

Python **3.9 or newer** (tested on 3.12).

## 3. Required packages

Listed in `requirements.txt`:

| Package | Used for |
|---|---|
| streamlit | the whole user interface |
| pandas | tables, filtering, report frames |
| plotly | dashboard and KPI charts |
| openpyxl | Excel export |
| psycopg[binary] | PostgreSQL driver — only used for the cloud deployment |

SQLite ships with Python, so there is no database server to install.

## 4. Activation is required - there is no trial

* Registering a gym creates a `licenses` row with `status = UNLICENSED`. Sign-up
  works, but **every module stays locked** and the activation screen appears
  straight away.
* The user enters the licence key issued for their gym; the software then unlocks
  for **1 year** from that date.
* Nothing is deleted while a copy is unlicensed or after a licence expires — the
  data waits, and a valid key restores full access exactly as it was.
* **Clock tampering is blocked.** Each page load writes a monotonic
  `last_seen_ts`. Moving the computer clock backwards by more than 6 hours raises
  a tamper flag and shows a warning; the reference time never walks backwards, so
  expired licence days cannot be won back. Moving the clock forward only brings
  the expiry closer.

## 5. How license activation works

1. The customer sends you their **gym name** and **registered mobile** exactly as
   they appear in Settings → Gym Profile.
2. You generate their key on your own machine:

   ```bash
   python tools/keygen.py "Iron Paradise Gym" 9876543210
   # SNGYM-XXXX-XXXX-XXXX-XXXX
   ```

3. They enter it on the activation screen that appears right after sign-up (or
   later under **License Management**) along with the same gym name and mobile,
   then press **Activate license**. Renewal after a year works the same way.
4. Validity is **1 year** from the activation date — activate on 20-Aug-2026 and
   it expires 19-Aug-2027. Status, activation date, expiry date and remaining
   days are shown on the same page.

The key is an HMAC of the gym name and mobile using `VENDOR_SECRET` in
`license_manager.py`. **Change that secret before you ship, and never distribute
`tools/keygen.py` to customers** — together they can mint keys.

**Going online later:** implement `license_manager.verify_online()` to POST the
key to your licence server and return
`{"valid": bool, "expiry": "YYYY-MM-DD", "message": str}`. Nothing else in the
app changes; the offline check stays as the fallback when the server is
unreachable.

## 5b. Cloud deployment (Streamlit Cloud + PostgreSQL)

The same code runs on SQLite locally and on PostgreSQL in the cloud — the backend
is chosen automatically by the presence of a `DATABASE_URL` secret. A public demo
account with sample data can be switched on with `DEMO_MODE = true`.

See **DEPLOYMENT.md** for the full step-by-step: creating the database, pushing
to GitHub, deploying, and migrating existing local data with
`tools/migrate_sqlite_to_postgres.py`.

## 6. Where the database is stored

**Locally:** `data/gym_management.db` inside the project folder, persisting
across restarts. **On the cloud:** the PostgreSQL database named in
`DATABASE_URL`. Settings → Backup & restore shows which one is live.
Set the `SNGYM_DB` environment variable to point somewhere else (a shared drive,
for example). Member photos go to `data/photos/`, backups to `data/backups/`.

## 7. How to take a backup

**Settings → Backup & restore**

* **Create database backup** writes a timestamped, consistent copy into
  `data/backups/`.
* **Download the latest backup** saves it to the user's Downloads folder — put
  that file on a pen drive or cloud folder weekly.
* **Restore** validates the uploaded file first, saves the current database as
  `pre_restore_*.db`, and only then replaces it. Nothing is overwritten without a
  confirmation tick.

## 8. How to create the first Admin account

There is no default password to leak. The first person to open the app presses
**Create a gym account**, fills in the gym name, owner, mobile, email, username,
password and a security question, and that account becomes the **Admin**. The
activation screen appears immediately afterwards — enter the licence key to
unlock the software. Further logins are created in **Staff Management** with a role of
Manager, Receptionist or Trainer.

## 9. How to customize SN Softech Solutions branding

* App title, footer text and version: `APP_NAME`, `COMPANY`, `VERSION` at the top
  of `app.py`.
* Colours, fonts, sidebar and card styling: `theme.py` (the `CSS` block and the
  `MENU` list, which holds each menu item's icon, label and accent colour).
* Support line on the licence screens: `SUPPORT_CONTACT` in `license_manager.py`.
* The gym's own logo, address, GST number and receipt footer: **Settings → Gym
  Profile** — these appear on every printed receipt and report.
* Drop a company logo image into `assets/logo/` if you want to swap the header
  emblem for artwork.

## 10. How to package the software for Windows later

The cleanest route for a Streamlit app:

1. Install the toolchain on a Windows machine:
   `pip install -r requirements.txt pyinstaller`
2. Create a launcher `run_gym.py`:

   ```python
   import os, sys, streamlit.web.cli as stcli
   here = os.path.dirname(os.path.abspath(__file__))
   sys.argv = ["streamlit", "run", os.path.join(here, "app.py"),
               "--global.developmentMode=false"]
   sys.exit(stcli.main())
   ```

3. Build it:

   ```bat
   pyinstaller --noconfirm --onedir --name "SN Gym Management" ^
     --add-data "modules;modules" --add-data "assets;assets" ^
     --collect-all streamlit --collect-all plotly run_gym.py
   ```

4. Ship the `dist\SN Gym Management` folder with a desktop shortcut. Keep the
   `data` folder outside the install directory (set `SNGYM_DB`) so an upgrade
   never touches customer data.

For a lighter option, install Python on the gym PC and ship a one-line
`start_gym.bat` containing `streamlit run app.py`.

---

## Project structure

```
SN_Gym_Management/
├── app.py                 # entry point: auth, licence gate, sidebar, routing
├── database.py            # schema, connection helpers, backup/restore
├── auth.py                # PBKDF2 hashing, login, roles, permissions
├── license_manager.py     # key generation/verification, clock guard
├── utils.py               # validation, formatting, Excel/print, UI helpers
├── reports.py             # all KPI and report queries (no UI)
├── theme.py               # palette, CSS, sidebar menu definition
├── demo_data.py           # optional sample gym
├── demo_setup.py          # public demo account bootstrap (DEMO_MODE)
├── DEPLOYMENT.md          # GitHub + Streamlit Cloud + Postgres guide
├── requirements.txt
├── INSTALL SETUP.bat      # Windows: one-time setup
├── START GYM SOFTWARE.bat # Windows: run the app
├── START ON NETWORK.bat   # Windows: run for reception + tablet
├── TAKE BACKUP.bat        # Windows: one-click database backup
├── assets/logo/
├── data/                  # gym_management.db, photos/, backups/
├── modules/               # one file per screen
│   ├── dashboard.py  members.py  membership.py  attendance.py
│   ├── trainers.py   payments.py expenses.py    products.py
│   └── reports_ui.py notifications.py settings.py
└── tools/
    ├── keygen.py          # vendor-only licence key generator
    ├── migrate_sqlite_to_postgres.py
    ├── smoke_test.py      # backend workflow tests
    └── ui_test.py         # renders every screen and fails on any error
```

The `modules/` folder is deliberately **not** called `pages/`: Streamlit turns any
folder named `pages/` into its own automatic navigation, which would fight the
custom sidebar.

## Roles

| Role | Access |
|---|---|
| Admin | Everything, including settings, staff and licence |
| Manager | Members, attendance, payments, expenses, products, reports |
| Receptionist | Members, sales, renewals, attendance, payments, products |
| Trainer | Assigned members, attendance, personal training |

## Testing

```bash
python tools/smoke_test.py   # backend checks: signup, activation lock, licence,
                             # tamper, CRUD, sale, renewal, PT, dues, reports,
                             # backup, roles
python tools/ui_test.py      # renders all 19 screens through Streamlit's AppTest

# Both suites also run against PostgreSQL:
export DATABASE_URL="postgresql://..." && python tools/smoke_test.py
```

Both suites pass on a clean checkout.

## Demo data

**Settings → Demo data → Load demo data** creates a sample gym (members,
trainers, memberships, 45 days of attendance, PT packages, expenses, products).
It only ever adds rows, and **Clear demo data** removes exactly those rows,
leaving anything you entered yourself untouched.

---

© SN Softech Solutions. SN Gym Management System v1.0.0.
