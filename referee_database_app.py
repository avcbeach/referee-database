import streamlit as st
import pandas as pd
from datetime import date, datetime
import os
import uuid
import base64
import requests
import io

# =========================
# CONFIG
# =========================

st.set_page_config(
    page_title="Beach Referee & Officials Database",
    page_icon="🏖️",
    layout="wide",
)

DATA_DIR = "data"
PHOTOS_DIR = os.path.join(DATA_DIR, "photos")
PASS_DIR = os.path.join(DATA_DIR, "passports")

REFEREES_FILE = os.path.join(DATA_DIR, "referees.csv")
EVENTS_FILE = os.path.join(DATA_DIR, "events.csv")
AVAIL_FILE = os.path.join(DATA_DIR, "availability.csv")
ASSIGN_FILE = os.path.join(DATA_DIR, "assignments.csv")  # nominations/appointments

GENDERS = ["", "Male", "Female"]
ZONES = ["", "E", "W", "SEA", "O", "C"]
POSITION_TYPES = ["Control Committee", "Referee", ""]
CC_ROLES = ["", "Technical Delegate", "Referee Coach", "Both"]
REF_LEVELS = ["", "FIVB", "AVC International", "AVC Candidate", "National"]
REF_TYPES = ["", "Indoor", "Beach", "Both"]
UNIFORM_SIZES = ["", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]


# =========================
# UTIL & GITHUB HELPERS
# =========================

def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    os.makedirs(PASS_DIR, exist_ok=True)


def new_id():
    return str(uuid.uuid4())


def github_config():
    """
    Read GitHub config from st.secrets.
    Returns dict or None if not configured.
    """
    try:
        gh = st.secrets["github"]
        token = gh.get("token", "").strip()
        owner = gh.get("repo_owner", "").strip()
        repo = gh.get("repo_name", "").strip()
        branch = gh.get("branch", "main").strip()
        if not (token and owner and repo):
            return None
        return {
            "token": token,
            "owner": owner,
            "repo": repo,
            "branch": branch,
        }
    except Exception:
        return None


def _github_api_url(cfg, path):
    # path like "data/referees.csv"
    safe_path = path.replace("\\", "/")
    return f"https://api.github.com/repos/{cfg['owner']}/{cfg['repo']}/contents/{safe_path}"


def github_read_file(path):
    """
    Read a file from GitHub repo. Returns bytes or None.
    `path` should be repo-relative, e.g. "data/referees.csv"
    """
    cfg = github_config()
    if not cfg:
        return None

    url = _github_api_url(cfg, path)
    headers = {
        "Authorization": f"token {cfg['token']}",
        "Accept": "application/vnd.github+json",
    }
    params = {"ref": cfg["branch"]}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
    except Exception:
        return None

    if r.status_code == 200:
        data = r.json()
        content = data.get("content", "")
        if content:
            try:
                return base64.b64decode(content)
            except Exception:
                return None
    elif r.status_code == 404:
        return None
    else:
        return None

    return None


def github_write_file(path, content_bytes, message):
    """
    Create or update a file in GitHub repo.
    path: repo-relative path, e.g. "data/referees.csv"
    content_bytes: bytes or str
    """
    cfg = github_config()
    if not cfg:
        return

    url = _github_api_url(cfg, path)
    headers = {
        "Authorization": f"token {cfg['token']}",
        "Accept": "application/vnd.github+json",
    }

    # Get existing SHA (if any)
    sha = None
    try:
        r_get = requests.get(url, headers=headers, params={"ref": cfg["branch"]}, timeout=10)
        if r_get.status_code == 200:
            sha = r_get.json().get("sha")
    except Exception:
        sha = None

    if isinstance(content_bytes, str):
        content_bytes = content_bytes.encode("utf-8")

    payload = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode("utf-8"),
        "branch": cfg["branch"],
    }
    if sha:
        payload["sha"] = sha

    try:
        r_put = requests.put(url, headers=headers, json=payload, timeout=10)
        if r_put.status_code not in (200, 201):
            pass
    except Exception:
        pass


def load_csv(path, columns):
    """
    Load CSV with GitHub support:
    - If GitHub configured and file exists there -> use remote
    - Else if local exists -> use local
    - Else -> empty with specified columns
    """
    ensure_dirs()
    df = None

    # Try GitHub first
    cfg = github_config()
    if cfg:
        content = github_read_file(path)
        if content is not None:
            try:
                df = pd.read_csv(io.BytesIO(content), dtype=str)
            except Exception:
                df = None

    # Fallback to local
    if df is None:
        if os.path.exists(path):
            df = pd.read_csv(path, dtype=str)
        else:
            df = pd.DataFrame(columns=columns)

    # Ensure all expected columns exist
    for c in columns:
        if c not in df.columns:
            df[c] = ""

    return df.fillna("")


def save_csv(path, df):
    """
    Save CSV locally and push to GitHub (if configured).
    """
    ensure_dirs()
    # Local save
    df.to_csv(path, index=False)

    # GitHub save
    cfg = github_config()
    if cfg:
        try:
            buf = io.StringIO()
            df.to_csv(buf, index=False)
            github_write_file(
                path,
                buf.getvalue(),
                f"Update {os.path.basename(path)} via referee app",
            )
        except Exception:
            pass


# =========================
# DATA LOADERS
# =========================

REFEREE_COLS = [
    "ref_id",
    "first_name",
    "last_name",
    "gender",
    "nationality",
    "zone",
    "birthdate",
    "fivb_id",
    "email",
    "phone",
    "origin_airport",
    "position_type",
    "cc_role",
    "ref_level",
    "course_year",
    "photo_file",
    "passport_file",
    "shirt_size",
    "shorts_size",
    "active",
    "type",
]

EVENT_COLS = [
    "event_id",
    "season",
    "start_date",
    "end_date",
    "event_name",
    "location",
    "destination_airport",
    "arrival_date",
    "departure_date",
    "requires_availability",
]

AVAIL_COLS = [
    "avail_id",
    "ref_id",
    "season",
    "event_id",
    "available",
    "airfare_estimate",
    "timestamp",
]

ASSIGN_COLS = [
    "assign_id",
    "ref_id",
    "event_id",
    "position",
]


def load_referees():
    df = load_csv(REFEREES_FILE, REFEREE_COLS)

    # Sync photo & passport files from GitHub if missing locally
    cfg = github_config()
    if cfg and not df.empty:
        for _, r in df.iterrows():
            for col in ["photo_file", "passport_file"]:
                rel = r.get(col, "")
                if isinstance(rel, str) and rel:
                    local_path = os.path.join(DATA_DIR, rel)
                    if not os.path.exists(local_path):
                        remote_path = os.path.join(DATA_DIR, rel).replace("\\", "/")
                        content = github_read_file(remote_path)
                        if content is not None:
                            os.makedirs(os.path.dirname(local_path), exist_ok=True)
                            try:
                                with open(local_path, "wb") as f:
                                    f.write(content)
                            except Exception:
                                pass

    return df


def save_referees(df):
    save_csv(REFEREES_FILE, df)


def load_events():
    df = load_csv(EVENTS_FILE, EVENT_COLS)
    if not df.empty:
        for col in ["start_date", "end_date", "arrival_date", "departure_date"]:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date.astype(str)
    return df


def save_events(df):
    save_csv(EVENTS_FILE, df)


def load_availability():
    return load_csv(AVAIL_FILE, AVAIL_COLS)


def save_availability(df):
    save_csv(AVAIL_FILE, df)


def load_assignments():
    return load_csv(ASSIGN_FILE, ASSIGN_COLS)


def save_assignments(df):
    save_csv(ASSIGN_FILE, df)


def referee_display_name(row):
    return f"{row['first_name']} {row['last_name']}".strip()


def _parse_date_str(s, fallback):
    """Helper: safe parse date string to datetime.date with fallback."""
    try:
        s = str(s)
        if not s or s == "NaT":
            return fallback
        return datetime.fromisoformat(s).date()
    except Exception:
        return fallback


# =========================
# ADMIN AUTH HELPERS
# =========================

def init_admin_session():
    """Initialize is_admin flag depending on whether an admin password is configured."""
    if "is_admin" not in st.session_state:
        # Try to read from secrets, else fallback to hardcoded default
        default_pwd = "avcbeach1234"
        try:
            _ = st.secrets["auth"]["admin_password"]
            st.session_state["is_admin"] = False
        except Exception:
            # no password configured in secrets → still protect with default
            st.session_state["is_admin"] = False
            st.session_state["admin_default_pwd"] = default_pwd


def admin_login_box():
    """Render admin login / logout controls in sidebar."""
    init_admin_session()

    # Determine password
    default_pwd = "avcbeach1234"
    try:
        admin_pwd = st.secrets["auth"]["admin_password"]
    except Exception:
        admin_pwd = default_pwd

    if st.session_state.get("is_admin", False):
        st.sidebar.success("Admin mode")
        if st.sidebar.button("Log out"):
            st.session_state["is_admin"] = False
            st.rerun()
    else:
        with st.sidebar.expander("🔑 Admin login"):
            pwd = st.text_input("Password", type="password", key="admin_pwd_input")
            if st.button("Login", key="admin_login_btn"):
                if pwd == admin_pwd:
                    st.session_state["is_admin"] = True
                    st.success("Login successful.")
                    st.rerun()
                else:
                    st.error("Incorrect password.")


def require_admin():
    """Protect an admin page. Call at the top of admin-only pages."""
    init_admin_session()
    if not st.session_state.get("is_admin", False):
        st.error("This page is for admin only. Please log in as admin from the sidebar.")
        st.stop()


# =========================
# PAGE: ADMIN – REFEREES
# =========================

def referee_display_name(row):
    fn = str(row.get("first_name", "")).strip()
    ln = str(row.get("last_name", "")).strip()
    nat = str(row.get("nationality", "")).strip()
    return f"{fn} {ln} - {nat}".strip()


def page_admin_referees():
    require_admin()
    st.title("👤 Admin – Referees & Officials")

    # Load data
    refs = load_referees()
    events = load_events()
    assignments = load_assignments()

    # ------------------------------
    # SESSION STATE
    # ------------------------------
    if "new_mode" not in st.session_state:
        st.session_state.new_mode = False

    if "selected_ref" not in st.session_state:
        st.session_state.selected_ref = None

    st.markdown("Use this page to **add or edit referees and officials**.")

    # ------------------------------
    # ➕ NEW BUTTON (clear form)
    # ------------------------------
    if st.button("➕ New Referee / Official"):
        st.session_state.new_mode = True
        st.session_state.selected_ref = None
        st.rerun()

    # ------------------------------
    # CATEGORY SELECTBOX (NEW)
    # ------------------------------
    st.markdown("### Filter by Category")
    category_choice = st.selectbox(
        "Position type",
        ["All", "Referee", "Control Committee"],
        key="admin_ref_category"
    )

    if not refs.empty:

        # Apply category filter
        if category_choice != "All":
            refs = refs[refs["position_type"] == category_choice]

        # Build display
        refs["display"] = refs.apply(referee_display_name, axis=1)

        # Sort alphabetically by FIRST name
        refs = refs.sort_values(by=["first_name", "last_name"])

        mapping = {row["display"]: row["ref_id"] for _, row in refs.iterrows()}
        name_list = list(mapping.keys())

    else:
        name_list = []
        mapping = {}

    # ------------------------------
    # SELECTION DROPDOWN (with reset)
    # ------------------------------
    if "select_ref_key" not in st.session_state:
        st.session_state.select_ref_key = 0

    # If NEW → force dropdown reset
    if st.session_state.new_mode:
        st.session_state.select_ref_key += 1

    sel = st.selectbox(
        "Select referee/official",
        [""] + name_list,
        key=f"ref_select_{st.session_state.select_ref_key}"
    )

    if sel in mapping:
        st.session_state.new_mode = False
        st.session_state.selected_ref = mapping[sel]

    # ------------------------------
    # DETERMINE SELECTED ROW
    # ------------------------------
    if st.session_state.new_mode:
        row = None
    elif st.session_state.selected_ref:
        row = refs[refs["ref_id"] == st.session_state.selected_ref].iloc[0]
    else:
        row = None

    # ---------------------------------
    # NEW MODE → FORCE EMPTY FIELDS
    # ---------------------------------
    if row is None:
        row = {
            "ref_id": "",
            "first_name": "",
            "last_name": "",
            "gender": "",
            "nationality": "",
            "zone": "",
            "birthdate": "",
            "fivb_id": "",
            "email": "",
            "phone": "",
            "origin_airport": "",
            "position_type": "",
            "cc_role": "",
            "ref_level": "",
            "course_year": "",
            "shirt_size": "",
            "shorts_size": "",
            "active": "True",
            "type": ""
        }

    # ===============================
    # ===== FORM: REFEREE DATA =====
    # ===============================
    st.subheader("Referee / Official Information")

    with st.form("ref_form"):
        # Column sets
        c1, c2, c3 = st.columns(3)
        with c1:
            first_name = st.text_input("First name", value=row["first_name"] if row is not None else "")
            last_name = st.text_input("Last name", value=row["last_name"] if row is not None else "")
            gender = st.selectbox(
                "Gender", GENDERS,
                index=GENDERS.index(row["gender"]) if row is not None and row["gender"] in GENDERS else 0
            )

        with c2:
            # Alphabetical NOC list
            NOC_LIST = sorted([
               "", "AFG","ASA","AUS","BAN","BHU","BRN","BRU","CAM","CHN","COK","FIJ","FSM","GUM",
               "HKG","INA","IND","IRI","IRQ","JOR","JPN","KAZ","KGZ","KIR","KOR","KUW","LAO","LIB",
               "MAC","MAS","MDV","MGL","MSH","MYA","NEP","NIU","NMI","NRU","NZL","OMA","PAK","PAU",
               "PHI","PLE","PNG","PRK","QAT","SAM","SIN","SOL","SRI","SYR","TGA","THA","TJK","TKM",
               "TLS","TPE","TUV","UAE","UZB","VAN","VIE","YEM"
            ])

            nationality = st.selectbox(
               "Nationality", NOC_LIST,
               index=NOC_LIST.index(row["nationality"]) if row is not None and row["nationality"] in NOC_LIST else 0
            )

            zone = st.selectbox(
                "Zone", ZONES,
                index=ZONES.index(row["zone"]) if row is not None and row["zone"] in ZONES else 0
            )

            try:
                bd_default = (
                    datetime.strptime(row["birthdate"], "%Y-%m-%d").date()
                    if row is not None and row["birthdate"]
                    else date(1990, 1, 1)
                )
            except:
                bd_default = date(1990, 1, 1)

            birthdate = st.date_input(
                "Birthdate",
                value=bd_default,
                min_value=date(1900, 1, 1),
                max_value=date(2100, 12, 31)
            ).isoformat()

        with c3:
            fivb_id = st.text_input("FIVB ID", value=row["fivb_id"] if row is not None else "")
            email = st.text_input("Email", value=row["email"] if row is not None else "")
            phone = st.text_input("Phone", value=row["phone"] if row is not None else "")

        c4, c5, c6 = st.columns(3)
        with c4:
            origin_airport = st.text_input(
                "Origin airport (e.g. BKK, PEK)", value=row["origin_airport"] if row is not None else ""
            )
            position_type = st.selectbox(
                "Position", POSITION_TYPES,
                index=POSITION_TYPES.index(row["position_type"]) if row is not None and row["position_type"] in POSITION_TYPES else 2
            )

        with c5:
            cc_role = st.selectbox(
                "If Control Committee – Role", CC_ROLES,
                index=CC_ROLES.index(row["cc_role"]) if row is not None and row["cc_role"] in CC_ROLES else 0
            )
            ref_level = st.selectbox(
                "If Referee – Level", REF_LEVELS,
                index=REF_LEVELS.index(row["ref_level"]) if row is not None and row["ref_level"] in REF_LEVELS else 0
            )

        with c6:
            course_year = st.text_input("Course year (for referees)", value=row["course_year"] if row is not None else "")
            ref_type = st.selectbox("Type", REF_TYPES,
                index=REF_TYPES.index(row["type"]) if row is not None and row["type"] in REF_TYPES else 0
            )

        c7, c8 = st.columns(2)
        with c7:
            active = st.checkbox("Active", value=(row["active"] == "True") if row is not None else True)

            shirt_default = row["shirt_size"] if row is not None else ""
            if shirt_default not in UNIFORM_SIZES:
                shirt_default = ""
            shirt_size = st.selectbox("Shirt size", UNIFORM_SIZES, index=UNIFORM_SIZES.index(shirt_default))

        with c8:
            shorts_default = row["shorts_size"] if row is not None else ""
            if shorts_default not in UNIFORM_SIZES:
                shorts_default = ""
            shorts_size = st.selectbox("Shorts size", UNIFORM_SIZES, index=UNIFORM_SIZES.index(shorts_default))

            photo_file = st.file_uploader("Photo ID (optional)", type=["jpg", "jpeg", "png"])
            passport_file = st.file_uploader("Passport (optional)", type=["pdf", "jpg", "jpeg", "png"])

        submitted = st.form_submit_button("💾 Save")

    # ======================
    # SAVE LOGIC
    # ======================
    if submitted:
        if not first_name.strip() and not last_name.strip():
            st.error("Please enter at least first name or last name.")
            return

        ensure_dirs()

        # NEW
        if row is None:
            ref_id = new_id()
            photo_path = ""
            passport_path = ""

            # Save files
            if photo_file is not None:
                ext = os.path.splitext(photo_file.name)[1]
                fname = f"{ref_id}{ext}"
                photo_path = os.path.join("photos", fname)
                full_photo_path = os.path.join(DATA_DIR, photo_path)
                with open(full_photo_path, "wb") as f:
                    f.write(photo_file.getbuffer())

            if passport_file is not None:
                ext = os.path.splitext(passport_file.name)[1]
                fname = f"{ref_id}{ext}"
                passport_path = os.path.join("passports", fname)
                full_pass_path = os.path.join(DATA_DIR, passport_path)
                with open(full_pass_path, "wb") as f:
                    f.write(passport_file.getbuffer())

            new_row = pd.DataFrame([{
                "ref_id": ref_id,
                "first_name": first_name.strip(),
                "last_name": last_name.strip(),
                "gender": gender,
                "nationality": nationality.strip(),
                "zone": zone,
                "birthdate": birthdate,
                "fivb_id": fivb_id.strip(),
                "email": email.strip(),
                "phone": phone.strip(),
                "origin_airport": origin_airport.strip(),
                "position_type": position_type,
                "cc_role": cc_role,
                "ref_level": ref_level,
                "course_year": course_year.strip(),
                "photo_file": photo_path,
                "passport_file": passport_path,
                "shirt_size": shirt_size,
                "shorts_size": shorts_size,
                "active": str(active),
                "type": ref_type,
            }])

            refs = pd.concat([refs, new_row], ignore_index=True)
            save_referees(refs)
            st.success("Referee/official added ✅")

        else:
            # UPDATE
            idx = refs[refs["ref_id"] == row["ref_id"]].index[0]

            photo_path = refs.loc[idx, "photo_file"]
            passport_path = refs.loc[idx, "passport_file"]

            # update files
            if photo_file is not None:
                ext = os.path.splitext(photo_file.name)[1]
                fname = f"{row['ref_id']}{ext}"
                photo_path = os.path.join("photos", fname)
                full_photo_path = os.path.join(DATA_DIR, photo_path)
                with open(full_photo_path, "wb") as f:
                    f.write(photo_file.getbuffer())

            if passport_file is not None:
                ext = os.path.splitext(passport_file.name)[1]
                fname = f"{row['ref_id']}{ext}"
                passport_path = os.path.join("passports", fname)
                full_pass_path = os.path.join(DATA_DIR, passport_path)
                with open(full_pass_path, "wb") as f:
                    f.write(passport_file.getbuffer())

            # write fields
            refs.loc[idx, "first_name"] = first_name.strip()
            refs.loc[idx, "last_name"] = last_name.strip()
            refs.loc[idx, "gender"] = gender
            refs.loc[idx, "nationality"] = nationality.strip()
            refs.loc[idx, "zone"] = zone
            refs.loc[idx, "birthdate"] = birthdate
            refs.loc[idx, "fivb_id"] = fivb_id.strip()
            refs.loc[idx, "email"] = email.strip()
            refs.loc[idx, "phone"] = phone.strip()
            refs.loc[idx, "origin_airport"] = origin_airport.strip()
            refs.loc[idx, "position_type"] = position_type
            refs.loc[idx, "cc_role"] = cc_role
            refs.loc[idx, "ref_level"] = ref_level
            refs.loc[idx, "course_year"] = course_year.strip()
            refs.loc[idx, "photo_file"] = photo_path
            refs.loc[idx, "passport_file"] = passport_path
            refs.loc[idx, "shirt_size"] = shirt_size
            refs.loc[idx, "shorts_size"] = shorts_size
            refs.loc[idx, "active"] = str(active)
            refs.loc[idx, "type"] = ref_type

            save_referees(refs)
            st.success("Referee/official updated ✅")

        # RESET FORM AFTER SAVE
        st.session_state.new_mode = True
        st.session_state.selected_ref = None
        st.rerun()

    # ======================
    # DELETE SECTION
    # ======================
    if row is not None:
        st.markdown("---")
        st.subheader("🗑️ Delete this referee")

        ref_name = referee_display_name(row)
        st.warning(
            f"You are about to permanently delete **{ref_name}**.\n\n"
            "This will remove:\n"
            "- Their details\n"
            "- Availability\n"
            "- Assignments\n\n"
            "**This action cannot be undone.**"
        )

        confirm = st.checkbox("Yes, delete permanently.")

        if st.button("🗑️ Delete Referee") and confirm:
            refs = refs[refs["ref_id"] != row["ref_id"]]
            save_referees(refs)

            avail = load_availability()
            if not avail.empty:
                save_availability(avail[avail["ref_id"] != row["ref_id"]])

            assignments = load_assignments()
            if not assignments.empty:
                save_assignments(assignments[assignments["ref_id"] != row["ref_id"]])

            # Remove files
            if row.get("photo_file"):
                fp = os.path.join(DATA_DIR, row["photo_file"])
                if os.path.exists(fp):
                    os.remove(fp)

            if row.get("passport_file"):
                fp = os.path.join(DATA_DIR, row["passport_file"])
                if os.path.exists(fp):
                    os.remove(fp)

            st.success("Deleted successfully.")
            st.session_state.selected_ref = None
            st.session_state.new_mode = True
            st.rerun()

    # ======================
    # LIST REFS BY CATEGORY
    # ======================
    st.markdown("---")
    st.subheader("All Referees / Officials")

    if refs.empty:
        st.info("No data yet.")
    else:
        refs_sorted = refs.sort_values(by=["first_name", "last_name"])

        st.write("### 🟦 Referees")
        st.dataframe(
            refs_sorted[refs_sorted["position_type"] == "Referee"]
            [["first_name", "last_name", "ref_level", "nationality", "zone", "active"]],
            use_container_width=True,
        )

        st.write("### 🟩 Officials (Control Committee)")
        st.dataframe(
            refs_sorted[refs_sorted["position_type"] == "Control Committee"]
            [["first_name", "last_name", "cc_role", "nationality", "zone", "active"]],
            use_container_width=True,
        )


# =========================
# PAGE: REFEREE SEARCH (ADMIN ONLY)
# =========================

def page_referee_search():
    require_admin()
    st.title("🔎 Referee Search & Profile")

    refs = load_referees()
    if refs.empty:
        st.info("No referees in database yet.")
        return

    # ====================================
    # 1️⃣ SELECT CATEGORY
    # ====================================
    st.markdown("### 1️⃣ Select category")
    category = st.selectbox(
        "Category",
        ["Referee", "Control Committee"],
        key="search_category"
    )

    # Filter by category
    refs = refs[refs["position_type"] == category].copy()
    if refs.empty:
        st.info("No referees in this category.")
        return

    # Display name string
    refs["display"] = refs.apply(
        lambda r: f"{r['first_name']} {r['last_name']} ({r['nationality']})",
        axis=1
    )

    # ====================================
    # 2️⃣ FILTER SECTION
    # ====================================
    st.markdown("### 2️⃣ Filters")

    colA, colB, colC = st.columns(3)

    with colA:
        search_text = st.text_input(
            "Search name",
            "",
            key="filter_search"
        ).lower().strip()

    with colB:
        nationality_multi = st.multiselect(
            "Nationality (multi-select)",
            sorted(refs["nationality"].dropna().unique().tolist()),
            key="filter_nationality_multi"
        )

    with colC:
        zone_multi = st.multiselect(
            "Zone (multi-select)",
            sorted([z for z in refs["zone"].dropna().unique().tolist() if z]),
            key="filter_zone_multi"
        )

    colD, colE, colF = st.columns(3)

    with colD:
        gender_filter = st.selectbox(
            "Gender",
            ["All"] + sorted([g for g in refs["gender"].dropna().unique().tolist() if g]),
            key="filter_gender"
        )

    with colE:
        # Type: Indoor / Beach / Both
        type_filter = st.selectbox(
            "Type (Indoor / Beach / Both)",
            ["All"] + sorted([t for t in refs["type"].dropna().unique().tolist() if t]),
            key="filter_type"
        )

    with colF:
        active_filter = st.selectbox(
            "Active status",
            ["All", "Active", "Inactive"],
            key="filter_active"
        )

    colG, colH, colI = st.columns(3)

    with colG:
        reflevel_multi = st.multiselect(
            "Referee level (multi-select)",
            sorted([rl for rl in refs["ref_level"].dropna().unique().tolist() if rl]),
            key="filter_reflevel_multi"
        )

    with colH:
        ccrole_filter = st.selectbox(
            "CC Role",
            ["All"] + sorted([c for c in refs["cc_role"].dropna().unique().tolist() if c]),
            key="filter_ccrole"
        )

    with colI:
        courseyear_filter = st.selectbox(
            "Course year",
            ["All"] + sorted([cy for cy in refs["course_year"].dropna().unique().tolist() if str(cy).strip()]),
            key="filter_courseyear"
        )

    colJ, colK, colL = st.columns(3)

    with colJ:
        shirt_filter = st.selectbox(
            "Shirt size",
            ["All"] + sorted([s for s in refs["shirt_size"].dropna().unique().tolist() if s]),
            key="filter_shirt"
        )

    with colK:
        shorts_filter = st.selectbox(
            "Shorts size",
            ["All"] + sorted([s for s in refs["shorts_size"].dropna().unique().tolist() if s]),
            key="filter_shorts"
        )

    with colL:
        airport_filter = st.text_input(
            "Origin airport contains",
            "",
            key="filter_airport"
        ).strip().lower()

    # ====================================
    # APPLY FILTERS
    # ====================================
    filtered = refs.copy()

    # Name search
    if search_text:
        filtered = filtered[
            filtered["display"].str.lower().str.contains(search_text)
        ]

    # Nationality multi
    if nationality_multi:
        filtered = filtered[filtered["nationality"].isin(nationality_multi)]

    # Zone multi
    if zone_multi:
        filtered = filtered[filtered["zone"].isin(zone_multi)]

    # Gender
    if gender_filter != "All":
        filtered = filtered[filtered["gender"] == gender_filter]

    # Type
    if type_filter != "All":
        filtered = filtered[filtered["type"] == type_filter]

    # Active
    if active_filter == "Active":
        filtered = filtered[filtered["active"] == "True"]
    elif active_filter == "Inactive":
        filtered = filtered[filtered["active"] == "False"]

    # Referee level multi
    if reflevel_multi:
        filtered = filtered[filtered["ref_level"].isin(reflevel_multi)]

    # CC Role
    if ccrole_filter != "All":
        filtered = filtered[filtered["cc_role"] == ccrole_filter]

    # Course year
    if courseyear_filter != "All":
        filtered = filtered[filtered["course_year"] == courseyear_filter]

    # Shirt size
    if shirt_filter != "All":
        filtered = filtered[filtered["shirt_size"] == shirt_filter]

    # Shorts size
    if shorts_filter != "All":
        filtered = filtered[filtered["shorts_size"] == shorts_filter]

    # Origin airport contains
    if airport_filter:
        filtered = filtered[
            filtered["origin_airport"].fillna("").str.lower().str.contains(airport_filter)
        ]

    # Sort by first name then last name
    filtered = filtered.sort_values(["first_name", "last_name"])

    # ====================================
    # 3️⃣ FILTERED TABLE
    # ====================================
    st.markdown("### 3️⃣ Filtered name list")

    if filtered.empty:
        st.warning("No referees match your filters.")
        return

    table_cols = [
        "first_name",
        "last_name",
        "nationality",
        "zone",
        "gender",
        "position_type",
        "ref_level",
        "cc_role",
        "course_year",
        "fivb_id",
        "origin_airport",
        "shirt_size",
        "shorts_size",
        "type",
        "active",
    ]

    existing_cols = [c for c in table_cols if c in filtered.columns]

    st.dataframe(
        filtered[existing_cols].rename(columns={
            "first_name": "First Name",
            "last_name": "Last Name",
            "nationality": "NOC",
            "zone": "Zone",
            "gender": "Gender",
            "position_type": "Position",
            "ref_level": "Ref Level",
            "cc_role": "CC Role",
            "course_year": "Course Year",
            "fivb_id": "FIVB ID",
            "origin_airport": "Airport",
            "shirt_size": "Shirt",
            "shorts_size": "Shorts",
            "type": "Type",
            "active": "Active",
        }),
        use_container_width=True,
    )

    # ====================================
    # 4️⃣ SELECT REFEREE PROFILE
    # ====================================
    st.markdown("### 4️⃣ Select name to view profile")

    select_options = list(filtered["display"])
    sel_label = st.selectbox(
        "Select referee",
        select_options,
        key="profile_select"
    )

    sel_id = filtered[filtered["display"] == sel_label].iloc[0]["ref_id"]
    prof = refs[refs["ref_id"] == sel_id].iloc[0]

    # ====================================
    # 5️⃣ PROFILE DISPLAY
    # ====================================
    colL, colR = st.columns([2, 1])

    with colL:
        st.markdown(f"## {prof['first_name']} {prof['last_name']}")
        st.write(f"**Gender:** {prof['gender']}")
        st.write(f"**Nationality:** {prof['nationality']}")
        st.write(f"**Zone:** {prof['zone']}")
        st.write(f"**Position:** {prof['position_type']}")
        if prof["position_type"] == "Control Committee":
            st.write(f"**CC Role:** {prof['cc_role']}")
        if prof["position_type"] == "Referee":
            st.write(f"**Referee level:** {prof['ref_level']}")
        st.write(f"**Type:** {prof['type']}")
        st.write(f"**Shirt size:** {prof['shirt_size']}")
        st.write(f"**Shorts size:** {prof['shorts_size']}")
        st.write(f"**Birthdate:** {prof['birthdate']}")
        st.write(f"**Course year:** {prof['course_year']}")
        st.write(f"**FIVB ID:** {prof['fivb_id']}")
        st.write(f"**Origin airport:** {prof['origin_airport']}")
        st.write(f"**Email:** {prof['email']}")
        st.write(f"**Phone:** {prof['phone']}")
        st.write(f"**Active:** {prof['active']}")

    with colR:
        st.markdown("#### Photo ID")
        photo_rel = prof.get("photo_file", "")
        if isinstance(photo_rel, str) and photo_rel:
            photo_path = os.path.join(DATA_DIR, photo_rel)
            if os.path.exists(photo_path):
                st.image(photo_path, use_container_width=True)
            else:
                st.caption("Photo path saved, but file not found locally.")
        else:
            st.caption("No photo uploaded.")

        st.markdown("#### Passport (Admin only)")
        is_admin = st.session_state.get("is_admin", False)

        if not is_admin:
            st.caption("Passport is private and only visible to administrators.")
        else:
            pass_rel = prof.get("passport_file", "")
            if isinstance(pass_rel, str) and pass_rel:
                pass_path = os.path.join(DATA_DIR, pass_rel)
                if os.path.exists(pass_path):
                    ext = os.path.splitext(pass_path)[1].lower()
                    try:
                        with open(pass_path, "rb") as f:
                            data = f.read()
                        if ext in [".jpg", ".jpeg", ".png"]:
                            st.image(pass_path, caption="Passport image", use_container_width=True)
                        elif ext == ".pdf":
                            st.download_button(
                                "Download passport (PDF)",
                                data=data,
                                file_name=os.path.basename(pass_path),
                                mime="application/pdf",
                            )
                        else:
                            st.download_button(
                                "Download passport file",
                                data=data,
                                file_name=os.path.basename(pass_path),
                            )
                    except Exception:
                        st.caption("Passport path saved, but file could not be opened.")
                else:
                    st.caption("Passport path saved, but file not found locally.")
            else:
                st.caption("No passport uploaded.")

    # ====================================
    # ✏️ EDIT REFEREE INFORMATION (INLINE)
    # ====================================
    st.markdown("---")
    st.subheader("✏️ Edit Referee Information")

    with st.form("edit_ref_form"):
        c1, c2 = st.columns(2)

        with c1:
            fn = st.text_input("First name", prof["first_name"])
            ln = st.text_input("Last name", prof["last_name"])
            gender = st.selectbox(
                "Gender",
                GENDERS,
                index=GENDERS.index(prof["gender"])
            )

            # Nationality list sorted
            NOC_LIST = sorted([
                "", "AFG","ASA","AUS","BAN","BHU","BRN","BRU","CAM","CHN","COK","FIJ",
                "FSM","GUM","HKG","INA","IND","IRI","IRQ","JOR","JPN","KAZ","KGZ","KIR",
                "KOR","KUW","LAO","LIB","MAC","MAS","MDV","MGL","MSH","MYA","NEP","NIU",
                "NMI","NRU","NZL","OMA","PAK","PAU","PHI","PLE","PNG","PRK","QAT","SAM",
                "SIN","SOL","SRI","SYR","TGA","THA","TJK","TKM","TLS","TPE","TUV","UAE",
                "UZB","VAN","VIE","YEM"
            ])

            nationality = st.selectbox(
                "Nationality",
                NOC_LIST,
                index=NOC_LIST.index(prof["nationality"]) if prof["nationality"] in NOC_LIST else 0
            )

            zone = st.selectbox(
                "Zone",
                ZONES,
                index=ZONES.index(prof["zone"]) if prof["zone"] in ZONES else 0
            )

            birthdate = st.text_input("Birthdate (YYYY-MM-DD)", prof["birthdate"])
            email = st.text_input("Email", prof["email"])
            phone = st.text_input("Phone", prof["phone"])

        with c2:
            origin_airport = st.text_input("Origin airport", prof["origin_airport"])

            position_type = st.selectbox(
                "Position",
                POSITION_TYPES,
                index=POSITION_TYPES.index(prof["position_type"])
                if prof["position_type"] in POSITION_TYPES else 0
            )

            cc_role = st.selectbox(
                "CC Role",
                CC_ROLES,
                index=CC_ROLES.index(prof["cc_role"])
                if prof["position_type"] == "Control Committee" else 0
            )

            ref_level = st.selectbox(
                "Referee level",
                REF_LEVELS,
                index=REF_LEVELS.index(prof["ref_level"])
                if prof["position_type"] == "Referee" else 0
            )

            course_year = st.text_input("Course year", prof["course_year"])

            shirt_size = st.selectbox(
                "Shirt size",
                UNIFORM_SIZES,
                index=UNIFORM_SIZES.index(prof["shirt_size"])
                if prof["shirt_size"] in UNIFORM_SIZES else 0
            )

            shorts_size = st.selectbox(
                "Shorts size",
                UNIFORM_SIZES,
                index=UNIFORM_SIZES.index(prof["shorts_size"])
                if prof["shorts_size"] in UNIFORM_SIZES else 0
            )

            active = st.checkbox("Active", value=(prof["active"] == "True"))

        save_edit = st.form_submit_button("💾 Save changes")

    if save_edit:
        refs_all = load_referees()
        idx = refs_all[refs_all["ref_id"] == prof["ref_id"]].index[0]

        refs_all.loc[idx, "first_name"] = fn.strip()
        refs_all.loc[idx, "last_name"] = ln.strip()
        refs_all.loc[idx, "gender"] = gender
        refs_all.loc[idx, "nationality"] = nationality
        refs_all.loc[idx, "zone"] = zone
        refs_all.loc[idx, "birthdate"] = birthdate.strip()
        refs_all.loc[idx, "email"] = email.strip()
        refs_all.loc[idx, "phone"] = phone.strip()
        refs_all.loc[idx, "origin_airport"] = origin_airport.strip()
        refs_all.loc[idx, "position_type"] = position_type
        refs_all.loc[idx, "cc_role"] = cc_role
        refs_all.loc[idx, "ref_level"] = ref_level
        refs_all.loc[idx, "course_year"] = course_year.strip()
        refs_all.loc[idx, "shirt_size"] = shirt_size
        refs_all.loc[idx, "shorts_size"] = shorts_size
        refs_all.loc[idx, "active"] = str(active)

        save_referees(refs_all)
        st.success("Referee updated successfully! 🔄")
        st.rerun()

    # ====================================
    # 📅 AVAILABILITY RESPONSES (INLINE)
    # ====================================
    st.markdown("---")
    st.subheader("📅 Availability Responses")

    avail = load_availability()

    # Filter only this referee
    my_avail = avail[avail["ref_id"] == prof["ref_id"]].copy()

    if my_avail.empty:
        st.caption("No availability submissions from this referee yet.")
    else:
        # Load event names
        events = load_events()

        if not events.empty:
            ev_small = events[[
                "event_id",
                "season",
                "start_date",
                "end_date",
                "event_name",
                "location"
            ]]

            # merge to show readable details
            my_avail = my_avail.merge(ev_small, on="event_id", how="left")

        # rename columns to readable names
        rename_map = {
            "season": "Season",
            "event_name": "Event",
            "location": "Location",
            "start_date": "Start",
            "end_date": "End",
            "available": "Available",
            "airfare_estimate": "Airfare Estimate",
            "timestamp": "Submitted At"
        }

        for old, new in rename_map.items():
            if old in my_avail.columns:
                my_avail = my_avail.rename(columns={old: new})

        # columns we want (only if exist)
        preferred_cols = [
            "Season",
            "Event",
            "Location",
            "Start",
            "End",
            "Available",
            "Airfare Estimate",
            "Submitted At"
        ]

        display_cols = [c for c in preferred_cols if c in my_avail.columns]

        # sorting: season + start date if available
        sort_cols = [c for c in ["Season", "Start"] if c in my_avail.columns]
        if sort_cols:
            my_avail = my_avail.sort_values(sort_cols)

        st.dataframe(
            my_avail[display_cols],
            use_container_width=True
        )

    # =========================
    # ADMIN-ONLY EVENT NOMINATIONS FOR THIS REFEREE
    # =========================
    if st.session_state.get("is_admin", False):
        st.markdown("---")
        st.subheader("📋 Event nominations for this referee")

        events = load_events()
        assignments = load_assignments()

        if events.empty:
            st.info("No events in the system yet. Add events on the 'Admin – Events' page.")
        else:
            ref_assign = assignments[assignments["ref_id"] == prof["ref_id"]].copy()
            if not ref_assign.empty:
                ev_small = events[[
                    "event_id",
                    "season",
                    "start_date",
                    "end_date",
                    "event_name",
                    "location",
                    "destination_airport",
                    "arrival_date",
                    "departure_date",
                ]].copy()
                merged = ref_assign.merge(ev_small, on="event_id", how="left")
                display_cols = [
                    "season",
                    "start_date",
                    "end_date",
                    "event_name",
                    "location",
                    "destination_airport",
                    "arrival_date",
                    "departure_date",
                    "position",
                ]
                st.markdown("**Current nominations / appointments:**")
                st.dataframe(
                    merged[display_cols].sort_values(["season", "start_date", "event_name"]),
                    use_container_width=True,
                )
            else:
                st.info("No nominations assigned to this referee yet.")

            st.markdown("#### ➕ Add nomination / appointment")

            seasons = sorted(events["season"].unique())
            season_filter = st.selectbox(
                "Filter events by season",
                ["All"] + seasons,
                key="assign_season_filter_profile",
            )

            if season_filter == "All":
                ev_filtered = events.copy()
            else:
                ev_filtered = events[events["season"] == season_filter].copy()

            if ev_filtered.empty:
                st.info("No events for this filter.")
            else:
                ev_filtered = ev_filtered.sort_values(["season", "start_date", "event_name"])
                labels = []
                mapping_ev = {}
                for _, ev in ev_filtered.iterrows():
                    label = f"{ev['season']} – {ev['start_date']} to {ev['end_date']} – {ev['event_name']} ({ev['location']})"
                    labels.append(label)
                    mapping_ev[label] = ev["event_id"]

                with st.form("add_assign_form_profile"):
                    ev_label = st.selectbox("Select event", labels)
                    position = st.text_input("Position (e.g. 1st Referee, 2nd Referee, TD, etc.)", value="")
                    submit_assign = st.form_submit_button("💾 Add nomination")

                if submit_assign:
                    ev_id = mapping_ev[ev_label]
                    if not position.strip():
                        st.error("Please input position.")
                    else:
                        dup = assignments[
                            (assignments["ref_id"] == prof["ref_id"]) &
                            (assignments["event_id"] == ev_id) &
                            (assignments["position"] == position.strip())
                        ]
                        if not dup.empty:
                            st.warning("This nomination already exists.")
                        else:
                            new_as = pd.DataFrame([{
                                "assign_id": new_id(),
                                "ref_id": prof["ref_id"],
                                "event_id": ev_id,
                                "position": position.strip(),
                            }])
                            assignments = pd.concat([assignments, new_as], ignore_index=True)
                            save_assignments(assignments)
                            st.success("Nomination added ✅")
                            st.rerun()

            st.markdown("#### 🗑️ Remove a nomination")
            ref_assign2 = assignments[assignments["ref_id"] == prof["ref_id"]].copy()
            if ref_assign2.empty:
                st.caption("No nominations to delete.")
            else:
                ev_small2 = events[["event_id", "season", "start_date", "end_date", "event_name", "location"]].copy()
                merged2 = ref_assign2.merge(ev_small2, on="event_id", how="left")
                labels2 = []
                id_map2 = {}
                for _, r2 in merged2.iterrows():
                    label2 = f"{r2['season']} – {r2['start_date']} to {r2['end_date']} – {r2['event_name']} ({r2['location']}) – {r2['position']}"
                    labels2.append(label2)
                    id_map2[label2] = r2["assign_id"]

                sel_del = st.selectbox("Select nomination to remove", ["(None)"] + labels2)
                if sel_del != "(None)":
                    if st.button("Delete selected nomination"):
                        ass_id = id_map2[sel_del]
                        assignments = assignments[assignments["assign_id"] != ass_id]
                        save_assignments(assignments)
                        st.success("Nomination removed ✅")
                        st.rerun()

# =========================
# PAGE: ADMIN – EVENTS
# =========================

def page_admin_events():
    require_admin()
    st.title("📅 Admin – Events per Season")

    events = load_events()

    st.markdown("Use this page to **add, edit, or delete events** for each season.")

    # ---------------------------------------------
    # ADD NEW EVENT
    # ---------------------------------------------
    st.subheader("➕ Add New Event")

    with st.form("add_event_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            season = st.text_input("Season", value=str(date.today().year))
        with c2:
            ev_name = st.text_input("Event name", value="")
        with c3:
            location = st.text_input("Location (city/country)", value="")

        destination_airport = st.text_input(
            "Destination airport (e.g., BKK, DOH)", value=""
        )

        # ============================
        # TOGGLE: DATE NOT CONFIRMED
        # ============================
        date_not_confirmed = st.checkbox("📅 Dates NOT confirmed yet")

        if not date_not_confirmed:
            st.markdown("### Event Dates")

            c4, c5 = st.columns(2)
            with c4:
                start_date = st.date_input("Start date", value=date.today())
                arrival_date = st.date_input("Arrival date", value=start_date)
            with c5:
                end_date = st.date_input("End date", value=date.today())
                departure_date = st.date_input("Departure date", value=end_date)
        else:
            start_date = None
            end_date = None
            arrival_date = None
            departure_date = None

        requires_availability = st.selectbox(
            "Requires Availability?",
            ["Yes", "No"],
            index=0
        )

        add_submit = st.form_submit_button("💾 Add Event")

    if add_submit:
        if not ev_name.strip():
            st.error("Event name is required.")
        else:
            if start_date and end_date and end_date < start_date:
                st.error("End date must be on or after start date.")
            elif arrival_date and departure_date and departure_date < arrival_date:
                st.error("Departure date must be on or after arrival date.")
            else:
                new_ev = pd.DataFrame([{
                    "event_id": new_id(),
                    "season": season.strip(),
                    "start_date": start_date.isoformat() if start_date else "",
                    "end_date": end_date.isoformat() if end_date else "",
                    "event_name": ev_name.strip(),
                    "location": location.strip(),
                    "destination_airport": destination_airport.strip(),
                    "arrival_date": arrival_date.isoformat() if arrival_date else "",
                    "departure_date": departure_date.isoformat() if departure_date else "",
                    "requires_availability": requires_availability,
                }])

                events = pd.concat([events, new_ev], ignore_index=True)
                save_events(events)
                st.success("Event added successfully ✅")
                st.rerun()

    # ---------------------------------------------
    # SHOW EVENTS
    # ---------------------------------------------
    st.markdown("---")
    st.subheader("📘 Existing Events")

    if events.empty:
        st.info("No events added yet.")
    else:
        df_disp = events.copy()
        df_disp = df_disp.sort_values(["season", "start_date", "event_name"])
        st.dataframe(df_disp.drop(columns=["event_id"]), use_container_width=True)

        # ---------------------------------------------
    # EDIT / DELETE EVENT
    # ---------------------------------------------
    if not events.empty:
        st.markdown("---")
        st.subheader("✏️ Edit or 🗑 Delete Event")

        events_sorted = events.sort_values(["season", "start_date", "event_name"])

        labels = []
        id_map = {}
        for _, r in events_sorted.iterrows():
            lbl = f"{r['season']} – {r['start_date']} to {r['end_date']} – {r['event_name']} ({r['location']})"
            labels.append(lbl)
            id_map[lbl] = r["event_id"]

        sel_label = st.selectbox("Select event", ["(None)"] + labels)

        if sel_label != "(None)":
            ev_id = id_map[sel_label]
            ev = events[events["event_id"] == ev_id].iloc[0]

            # Parse dates safely (may be blank)
            sd_val = _parse_date_str(ev.get("start_date", ""), date.today())
            ed_val = _parse_date_str(ev.get("end_date", ""), date.today())
            arr_val = _parse_date_str(ev.get("arrival_date", ""), sd_val)
            dep_val = _parse_date_str(ev.get("departure_date", ""), ed_val)

            st.markdown("### Edit Event")

            with st.form("edit_event_form"):
                # Event basics
                c1, c2, c3 = st.columns(3)
                with c1:
                    season_edit = st.text_input("Season", value=str(ev["season"]))
                with c2:
                    name_edit = st.text_input("Event name", value=str(ev["event_name"]))
                with c3:
                    loc_edit = st.text_input("Location (city/country)", value=str(ev["location"]))

                destination_edit = st.text_input(
                    "Destination airport (e.g., BKK, DOH)",
                    value=str(ev.get("destination_airport", "")),
                )

                # ============================
                # DATE NOT CONFIRMED TOGGLE
                # ============================
                date_not_confirmed_edit = st.checkbox(
                    "📅 Dates NOT confirmed yet",
                    value=(
                        not ev.get("start_date") 
                        and not ev.get("end_date")
                        and not ev.get("arrival_date")
                        and not ev.get("departure_date")
                    )
                )

                if not date_not_confirmed_edit:
                    st.markdown("### Event Dates")

                    c4, c5 = st.columns(2)
                    with c4:
                        sd_edit = st.date_input("Start date", value=sd_val)
                        arr_edit = st.date_input("Arrival date", value=arr_val)
                    with c5:
                        ed_edit = st.date_input("End date", value=ed_val)
                        dep_edit = st.date_input("Departure date", value=dep_val)
                else:
                    sd_edit = None
                    ed_edit = None
                    arr_edit = None
                    dep_edit = None

                req_edit = st.selectbox(
                    "Requires Availability?",
                    ["Yes", "No"],
                    index=["Yes", "No"].index(ev.get("requires_availability", "Yes"))
                )

                save_edit = st.form_submit_button("💾 Save Changes")

            if save_edit:
                if not name_edit.strip():
                    st.error("Event name is required.")
                elif sd_edit and ed_edit and ed_edit < sd_edit:
                    st.error("End date must be on or after start date.")
                elif arr_edit and dep_edit and dep_edit < arr_edit:
                    st.error("Departure date must be on or after arrival date.")
                else:
                    idx = events[events["event_id"] == ev_id].index[0]

                    events.loc[idx, "season"] = season_edit.strip()
                    events.loc[idx, "event_name"] = name_edit.strip()
                    events.loc[idx, "location"] = loc_edit.strip()
                    events.loc[idx, "destination_airport"] = destination_edit.strip()

                    events.loc[idx, "start_date"] = sd_edit.isoformat() if sd_edit else ""
                    events.loc[idx, "end_date"] = ed_edit.isoformat() if ed_edit else ""
                    events.loc[idx, "arrival_date"] = arr_edit.isoformat() if arr_edit else ""
                    events.loc[idx, "departure_date"] = dep_edit.isoformat() if dep_edit else ""

                    events.loc[idx, "requires_availability"] = req_edit

                    save_events(events)
                    st.success("Event updated successfully ✅")
                    st.rerun()

            st.markdown("---")
            st.subheader("🗑 Delete Event")

            confirm = st.checkbox("Yes, delete this event permanently.")

            if st.button("Delete Event") and confirm:
                events = events[events["event_id"] != ev_id]
                save_events(events)

                # Remove linked availability
                avail = load_availability()
                avail = avail[avail["event_id"] != ev_id]
                save_availability(avail)

                # Remove linked assignments
                assignments = load_assignments()
                assignments = assignments[assignments["event_id"] != ev_id]
                save_assignments(assignments)

                st.success("Event deleted successfully.")
                st.rerun()


# =========================
# PAGE: REFEREE AVAILABILITY FORM – PUBLIC
# =========================

def page_availability_form():
    st.title("📝 Referee / Official Availability Form")

    refs = load_referees()
    events = load_events()
    avail = load_availability()

    if refs.empty:
        st.warning("No referees found. Admin must add referees first.")
        return
    if events.empty:
        st.warning("No events found. Admin must add events first.")
        return

    st.markdown(
        """
Please complete your availability for AVC Beach Events.  
This form is **private** — only you and administrators can view your submission.
"""
    )

    # =====================================================
    # STEP 1 — CATEGORY SELECTION (Referee / Control Committee)
    # =====================================================
    st.markdown("### 1️⃣ Select your category")

    category = st.selectbox(
        "Are you a Referee or Control Committee?",
        ["", "Referee", "Control Committee"],
        index=0
    )

    if category == "":
        st.info("Please choose your category above.")
        return

    # Filter referees matching category
    refs_filtered = refs[refs["position_type"] == category].copy()
    if refs_filtered.empty:
        st.error(f"No {category} found in database.")
        return

    refs_filtered = refs_filtered.sort_values(["first_name", "last_name"])

    # Show only ID, Name (NAT)
    refs_filtered["display"] = refs_filtered.apply(
        lambda r: f"{r['first_name']} {r['last_name']} ({r['nationality']})",
        axis=1
    )

    # =====================================================
    # STEP 2 — REFEREE SELECT + IDENTITY VERIFY
    # =====================================================
    st.markdown("### 2️⃣ Select your name")

    ref_label = st.selectbox(
        "Your name",
        [""] + refs_filtered["display"].tolist()
    )

    if ref_label == "":
        st.info("Please select your name above.")
        return

    ref_row = refs_filtered[refs_filtered["display"] == ref_label].iloc[0]
    ref_id = ref_row["ref_id"]
    birth_on_file = str(ref_row.get("birthdate", "")).strip()

    if not birth_on_file:
        st.error("Your birthdate is not recorded yet in the system. Please contact the administrator at beachvolleyball@asianvolleyball.net")
        return

    st.markdown(f"### 👋 Hello **{ref_row['first_name']} {ref_row['last_name']}**")
    st.markdown("### 3️⃣ Verify your identity")

    birth_input = st.text_input("Enter your birthdate (YYYY-MM-DD)")

    if not birth_input:
        st.info("Please enter your birthdate to continue.")
        return

    if birth_input.strip() != birth_on_file:
        st.error("Birthdate does not match our records. Please check and try again.")
        return

    # =====================================================
    # STEP 3 — SELECT SEASON
    # =====================================================
    season_list = sorted(events["season"].unique())
    st.markdown("### 4️⃣ Choose the season")

    selected_season = st.selectbox("Season", season_list)

    season_events = events[events["season"] == selected_season].copy()
    season_events = season_events[season_events["requires_availability"] == "Yes"].copy()

    if season_events.empty:
        st.info("No events for this season require availability submissions.")
        return

    # Load previously saved availability
    avail_ref = avail[(avail["ref_id"] == ref_id) & (avail["season"] == str(selected_season))].copy()
    avail_map = {}
    if not avail_ref.empty:
        for _, r in avail_ref.iterrows():
            eid = r["event_id"]
            avail_map[eid] = {
                "available": str(r.get("available", "")).lower() == "true",
                "airfare_estimate": r.get("airfare_estimate", "")
            }

    # =====================================================
    # STEP 4 — EVENT AVAILABILITY INPUT
    # =====================================================
    st.markdown(f"### 5️⃣ Availability for **Season {selected_season}**")

    per_event_inputs = []
    season_events = season_events.sort_values(["start_date", "event_name"])

    for _, ev in season_events.iterrows():
        ev_id = ev["event_id"]
        ev_name = ev["event_name"]

        defaults = avail_map.get(ev_id, {"available": False, "airfare_estimate": ""})
        default_available = defaults["available"]
        default_airfare = defaults["airfare_estimate"]

        # Event box
        st.markdown("---")
        st.markdown(f"#### 📌 {ev_name} ({ev['location']})")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Start date:** {ev.get('start_date', '')}")
            st.write(f"**End date:** {ev.get('end_date', '')}")
        with col2:
            st.write(f"**Arrival date:** {ev.get('arrival_date', '')}")
            st.write(f"**Departure date:** {ev.get('departure_date', '')}")
        with col3:
            st.write(f"**Destination airport:** {ev.get('destination_airport', '')}")

        # Inputs
        available = st.checkbox(
            f"Available for this event",
            value=default_available,
            key=f"avail_{ev_id}"
        )

        airfare_estimate = st.text_input(
            "Estimated airfare (optional)",
            value=str(default_airfare),
            key=f"airfare_{ev_id}"
        )

        per_event_inputs.append({
            "event_id": ev_id,
            "available": available,
            "airfare_estimate": airfare_estimate.strip(),
        })

    # =====================================================
    # STEP 5 — SUBMIT
    # =====================================================
    if st.button("📨 Submit availability"):
        avail = avail[~((avail["ref_id"] == ref_id) & (avail["season"] == str(selected_season)))]
        now_str = datetime.utcnow().isoformat()

        new_rows = []
        for item in per_event_inputs:
            new_rows.append({
                "avail_id": new_id(),
                "ref_id": ref_id,
                "season": str(selected_season),
                "event_id": item["event_id"],
                "available": str(bool(item["available"])),
                "airfare_estimate": item["airfare_estimate"],
                "timestamp": now_str,
            })

        if new_rows:
            avail = pd.concat([avail, pd.DataFrame(new_rows)], ignore_index=True)

        save_availability(avail)
        st.success("Thank you! Your availability has been recorded. ✅")

    # =====================================================
    # STEP 6 — REFEREE SUMMARY
    # =====================================================
    st.markdown("### 📄 Your saved availability (summary)")
    avail_me = load_availability()
    avail_me = avail_me[(avail_me["ref_id"] == ref_id) & (avail_me["season"] == str(selected_season))]

    if avail_me.empty:
        st.info("No previous availability saved for this season.")
    else:
        events_small = events[["event_id", "season", "start_date", "end_date", "event_name", "location"]]
        merged = avail_me.merge(events_small, on=["event_id", "season"], how="left")
        merged = merged.sort_values(["start_date", "event_name"])
        view_cols = [
            "start_date",
            "end_date",
            "event_name",
            "location",
            "available",
            "airfare_estimate",
            "timestamp",
        ]
        st.dataframe(merged[view_cols], use_container_width=True)


# =========================
# PAGE: ADMIN – VIEW AVAILABILITY
# =========================

def page_admin_availability():
    require_admin()
    st.title("📊 Admin – Availability & Nominations Overview")

    refs = load_referees()
    events = load_events()
    avail = load_availability()
    assignments = load_assignments()

    if refs.empty or events.empty:
        st.info("No data available yet.")
        return

    # Build season selector
    seasons = sorted(events["season"].unique())
    selected_season = st.selectbox("Select season", seasons)

    # Filter by season
    season_events = events[events["season"] == selected_season]
    season_avail = avail[avail["season"] == str(selected_season)]
    season_assign = assignments.copy()

    # Build merged base table
    refs_small = refs[["ref_id", "first_name", "last_name", "nationality", "zone", "position_type"]]
    ev_small = season_events[["event_id", "season", "event_name", "start_date", "end_date", "location"]]

    merged = season_avail.merge(refs_small, on="ref_id", how="left")
    merged = merged.merge(ev_small, on=["event_id", "season"], how="left")

    # Add nominated rows not present in availability
    nominated_extra = []
    for _, a in season_assign.iterrows():
        if (a["ref_id"], a["event_id"]) not in zip(merged["ref_id"], merged["event_id"]):
            ref_row = refs_small[refs_small["ref_id"] == a["ref_id"]]
            ev_row = ev_small[ev_small["event_id"] == a["event_id"]]
            if not ref_row.empty and not ev_row.empty:
                r = ref_row.iloc[0]
                e = ev_row.iloc[0]
                nominated_extra.append({
                    "ref_id": a["ref_id"],
                    "event_id": a["event_id"],
                    "season": selected_season,
                    "event_name": e["event_name"],
                    "start_date": e["start_date"],
                    "end_date": e["end_date"],
                    "location": e["location"],
                    "available": "",
                    "airfare_estimate": "",
                    "timestamp": "",
                    "first_name": r["first_name"],
                    "last_name": r["last_name"],
                    "nationality": r["nationality"],
                    "zone": r["zone"],
                    "position_type": r["position_type"],
                })

    if nominated_extra:
        merged = pd.concat([merged, pd.DataFrame(nominated_extra)], ignore_index=True)

    if merged.empty:
        st.info("No availability or nominations found for this season.")
        return

    # Compute status
    assign_pairs = set(zip(season_assign["ref_id"], season_assign["event_id"]))

    def get_status(row):
        key = (row["ref_id"], row["event_id"])
        if key in assign_pairs:
            return "Nominated"
        if str(row["available"]).lower() == "true":
            return "Available"
        if str(row["available"]).lower() == "false":
            return "Not Available"
        return "Unknown"

    merged["status"] = merged.apply(get_status, axis=1)
    merged["ref_name"] = merged["first_name"] + " " + merged["last_name"]

    st.markdown("## 🔍 Filters")

    col1, col2, col3 = st.columns(3)
    with col1:
        event_filter = st.selectbox(
            "Filter by event",
            ["All"] + sorted(season_events["event_name"].unique())
        )
    with col2:
        nat_filter = st.selectbox(
            "Filter by nationality",
            ["All"] + sorted(merged["nationality"].dropna().unique())
        )
    with col3:
        zone_filter = st.selectbox(
            "Filter by zone",
            ["All"] + sorted(merged["zone"].dropna().unique())
        )

    col4, col5 = st.columns(2)
    with col4:
        pt_filter = st.selectbox(
            "Filter by position",
            ["All", "Referee", "Control Committee"]
        )
    with col5:
        status_filter = st.selectbox(
            "Filter by status",
            ["All", "Nominated", "Available", "Not Available", "Unknown"]
        )

    # Apply filters
    df = merged.copy()

    if event_filter != "All":
        df = df[df["event_name"] == event_filter]

    if nat_filter != "All":
        df = df[df["nationality"] == nat_filter]

    if zone_filter != "All":
        df = df[df["zone"] == zone_filter]

    if pt_filter != "All":
        df = df[df["position_type"] == pt_filter]

    if status_filter != "All":
        df = df[df["status"] == status_filter]

    df = df.sort_values(["start_date", "event_name", "ref_name"])

    st.markdown("## 📋 Availability & Nominations Table")

    view_cols = [
        "event_name",
        "location",
        "start_date",
        "end_date",
        "ref_name",
        "nationality",
        "zone",
        "position_type",
        "status",
        "airfare_estimate",
        "timestamp",
    ]

    st.dataframe(df[view_cols], use_container_width=True)



# =========================
# MAIN
# =========================

def main():
    st.sidebar.title("🏖️ Beach Referee DB")

    admin_login_box()
    init_admin_session()
    is_admin = st.session_state.get("is_admin", False)

    if is_admin:
        page = st.sidebar.radio(
            "Go to",
            [
                "Referee Availability Form",
                "Referee Search",
                "Admin – Referees",
                "Admin – Events",
                "Admin – View Availability",
            ],
        )
    else:
        page = st.sidebar.radio(
            "Go to",
            [
                "Referee Availability Form",
            ],
        )

    if page == "Admin – Referees":
        page_admin_referees()
    elif page == "Admin – Events":
        page_admin_events()
    elif page == "Admin – View Availability":
        page_admin_availability()
    elif page == "Referee Search":
        page_referee_search()
    elif page == "Referee Availability Form":
        page_availability_form()


if __name__ == "__main__":
    main()
