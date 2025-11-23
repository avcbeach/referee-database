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

def page_admin_referees():
    require_admin()
    st.title("👤 Admin – Referees & Officials")

    refs = load_referees()
    events = load_events()
    assignments = load_assignments()

    st.markdown("Use this page to **add or edit referees and officials**.")

    # Selection for edit
    if refs.empty:
        options = ["<New>"]
        mapping = {}
    else:
        refs["display"] = refs.apply(referee_display_name, axis=1)
        refs = refs.sort_values("display")
        mapping = {row["display"]: row["ref_id"] for _, row in refs.iterrows()}
        options = ["<New>"] + list(mapping.keys())

    sel = st.selectbox("Select referee/official", options)
    sel_id = mapping.get(sel)
    if sel_id:
        row = refs[refs["ref_id"] == sel_id].iloc[0]
    else:
        row = None

    st.subheader("Referee / Official Information")
    with st.form("ref_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            first_name = st.text_input("First name", value=row["first_name"] if row is not None else "")
            last_name = st.text_input("Last name", value=row["last_name"] if row is not None else "")
            gender = st.selectbox(
                "Gender",
                GENDERS,
                index=GENDERS.index(row["gender"]) if row is not None and row["gender"] in GENDERS else 0,
            )
        with c2:
            nationality = st.text_input(
                "Nationality (e.g. THA, CHN)",
                value=row["nationality"] if row is not None else "",
            )
            zone = st.selectbox(
                "Zone",
                ZONES,
                index=ZONES.index(row["zone"]) if row is not None and row["zone"] in ZONES else 0,
            )
            birthdate = st.text_input(
                "Birthdate (YYYY-MM-DD)",
                value=row["birthdate"] if row is not None else "",
            )
        with c3:
            fivb_id = st.text_input(
                "FIVB ID",
                value=row["fivb_id"] if row is not None else "",
            )
            email = st.text_input(
                "Email",
                value=row["email"] if row is not None else "",
            )
            phone = st.text_input(
                "Phone",
                value=row["phone"] if row is not None else "",
            )

        c4, c5, c6 = st.columns(3)
        with c4:
            origin_airport = st.text_input(
                "Origin airport (e.g. BKK, PEK)",
                value=row["origin_airport"] if row is not None else "",
            )
            position_type = st.selectbox(
                "Position",
                POSITION_TYPES,
                index=POSITION_TYPES.index(row["position_type"]) if row is not None and row["position_type"] in POSITION_TYPES else 2,
            )
        with c5:
            cc_role = st.selectbox(
                "If Control Committee – Role",
                CC_ROLES,
                index=CC_ROLES.index(row["cc_role"]) if row is not None and row["cc_role"] in CC_ROLES else 0,
                help="Technical Delegate / Referee Coach / Both (for Control Committee only)",
            )
            ref_level = st.selectbox(
                "If Referee – Level",
                REF_LEVELS,
                index=REF_LEVELS.index(row["ref_level"]) if row is not None and row["ref_level"] in REF_LEVELS else 0,
            )
        with c6:
            course_year = st.text_input(
                "Course year (for referees)",
                value=row["course_year"] if row is not None else "",
            )
            ref_type = st.selectbox(
                "Type",
                REF_TYPES,
                index=REF_TYPES.index(row["type"]) if row is not None and row["type"] in REF_TYPES else 0,
            )

        c7, c8 = st.columns(2)
        with c7:
            active = st.checkbox(
                "Active",
                value=(row["active"] == "True") if row is not None else True,
            )
            shirt_default = row["shirt_size"] if row is not None else ""
            if shirt_default not in UNIFORM_SIZES:
                shirt_default = ""
            shirt_size = st.selectbox(
                "Shirt size",
                UNIFORM_SIZES,
                index=UNIFORM_SIZES.index(shirt_default),
            )
        with c8:
            shorts_default = row["shorts_size"] if row is not None else ""
            if shorts_default not in UNIFORM_SIZES:
                shorts_default = ""
            shorts_size = st.selectbox(
                "Shorts size",
                UNIFORM_SIZES,
                index=UNIFORM_SIZES.index(shorts_default),
            )
            photo_file = st.file_uploader("Photo ID (optional)", type=["jpg", "jpeg", "png"])
            passport_file = st.file_uploader("Passport (optional)", type=["pdf", "jpg", "jpeg", "png"])

        submitted = st.form_submit_button("💾 Save")

    if submitted:
        if not first_name.strip() and not last_name.strip():
            st.error("Please enter at least first name or last name.")
            return

        ensure_dirs()

        if row is None:
            # New referee
            ref_id = new_id()
            photo_path = ""
            passport_path = ""

            if photo_file is not None:
                ext = os.path.splitext(photo_file.name)[1]
                fname = f"{ref_id}{ext}"
                photo_path = os.path.join("photos", fname)
                full_photo_path = os.path.join(DATA_DIR, photo_path)
                with open(full_photo_path, "wb") as f:
                    f.write(photo_file.getbuffer())
                cfg = github_config()
                if cfg:
                    github_write_file(
                        os.path.join(DATA_DIR, photo_path),
                        photo_file.getbuffer().tobytes(),
                        f"Add photo {fname} via referee app",
                    )

            if passport_file is not None:
                ext = os.path.splitext(passport_file.name)[1]
                fname = f"{ref_id}{ext}"
                passport_path = os.path.join("passports", fname)
                full_pass_path = os.path.join(DATA_DIR, passport_path)
                with open(full_pass_path, "wb") as f:
                    f.write(passport_file.getbuffer())
                cfg = github_config()
                if cfg:
                    github_write_file(
                        os.path.join(DATA_DIR, passport_path),
                        passport_file.getbuffer().tobytes(),
                        f"Add passport {fname} via referee app",
                    )

            new_row = pd.DataFrame([{
                "ref_id": ref_id,
                "first_name": first_name.strip(),
                "last_name": last_name.strip(),
                "gender": gender,
                "nationality": nationality.strip(),
                "zone": zone,
                "birthdate": birthdate.strip(),
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
            # Update existing
            idx = refs[refs["ref_id"] == row["ref_id"]].index[0]
            photo_path = refs.loc[idx, "photo_file"]
            passport_path = refs.loc[idx, "passport_file"]

            if photo_file is not None:
                ext = os.path.splitext(photo_file.name)[1]
                fname = f"{row['ref_id']}{ext}"
                photo_path = os.path.join("photos", fname)
                full_photo_path = os.path.join(DATA_DIR, photo_path)
                with open(full_photo_path, "wb") as f:
                    f.write(photo_file.getbuffer())
                cfg = github_config()
                if cfg:
                    github_write_file(
                        os.path.join(DATA_DIR, photo_path),
                        photo_file.getbuffer().tobytes(),
                        f"Update photo {fname} via referee app",
                    )

            if passport_file is not None:
                ext = os.path.splitext(passport_file.name)[1]
                fname = f"{row['ref_id']}{ext}"
                passport_path = os.path.join("passports", fname)
                full_pass_path = os.path.join(DATA_DIR, passport_path)
                with open(full_pass_path, "wb") as f:
                    f.write(passport_file.getbuffer())
                cfg = github_config()
                if cfg:
                    github_write_file(
                        os.path.join(DATA_DIR, passport_path),
                        passport_file.getbuffer().tobytes(),
                        f"Update passport {fname} via referee app",
                    )

            refs.loc[idx, "first_name"] = first_name.strip()
            refs.loc[idx, "last_name"] = last_name.strip()
            refs.loc[idx, "gender"] = gender
            refs.loc[idx, "nationality"] = nationality.strip()
            refs.loc[idx, "zone"] = zone
            refs.loc[idx, "birthdate"] = birthdate.strip()
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

    # Delete referee
    if row is not None:
        st.markdown("---")
        st.subheader("🗑️ Delete this referee")

        ref_name = referee_display_name(row)
        st.warning(
            "You are about to permanently delete **%s**.\n\n"
            "This will remove:\n"
            "- Their personal details\n"
            "- All availability submissions linked to this referee\n"
            "- All event nominations linked to this referee\n\n"
            "This action cannot be undone." % ref_name
        )

        confirm_delete = st.checkbox("Yes, I want to delete this referee permanently.")

        if st.button("🗑️ Delete Referee") and confirm_delete:
            refs = refs[refs["ref_id"] != row["ref_id"]]

            avail = load_availability()
            if not avail.empty:
                avail = avail[avail["ref_id"] != row["ref_id"]]
                save_availability(avail)

            assignments = load_assignments()
            if not assignments.empty:
                assignments = assignments[assignments["ref_id"] != row["ref_id"]]
                save_assignments(assignments)

            photo_path = row.get("photo_file", "")
            if isinstance(photo_path, str) and photo_path:
                full_photo = os.path.join(DATA_DIR, photo_path)
                if os.path.exists(full_photo):
                    os.remove(full_photo)

            passport_path = row.get("passport_file", "")
            if isinstance(passport_path, str) and passport_path:
                full_pass = os.path.join(DATA_DIR, passport_path)
                if os.path.exists(full_pass):
                    os.remove(full_pass)

            save_referees(refs)
            st.success("Referee deleted successfully ✅")
            st.rerun()

    # Event nominations per referee
    if row is not None:
        st.markdown("---")
        st.subheader("📋 Event nominations for this referee")

        events = load_events()
        assignments = load_assignments()

        if events.empty:
            st.info("No events in the system yet. Add events on the 'Admin – Events' page.")
        else:
            ref_assign = assignments[assignments["ref_id"] == row["ref_id"]].copy()
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
                key="assign_season_filter",
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

                with st.form("add_assign_form"):
                    ev_label = st.selectbox("Select event", labels)
                    position = st.text_input("Position (e.g. 1st Referee, 2nd Referee, TD, etc.)", value="")
                    submit_assign = st.form_submit_button("💾 Add nomination")

                if submit_assign:
                    ev_id = mapping_ev[ev_label]
                    if not position.strip():
                        st.error("Please input position.")
                    else:
                        dup = assignments[
                            (assignments["ref_id"] == row["ref_id"]) &
                            (assignments["event_id"] == ev_id) &
                            (assignments["position"] == position.strip())
                        ]
                        if not dup.empty:
                            st.warning("This nomination already exists.")
                        else:
                            new_as = pd.DataFrame([{
                                "assign_id": new_id(),
                                "ref_id": row["ref_id"],
                                "event_id": ev_id,
                                "position": position.strip(),
                            }])
                            assignments = pd.concat([assignments, new_as], ignore_index=True)
                            save_assignments(assignments)
                            st.success("Nomination added ✅")
                            st.rerun()

            st.markdown("#### 🗑️ Remove a nomination")
            ref_assign2 = assignments[assignments["ref_id"] == row["ref_id"]].copy()
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

    # Quick listing
    st.markdown("---")
    st.subheader("All Referees / Officials")
    if refs.empty:
        st.info("No data yet.")
    else:
        view_cols = [
            "first_name",
            "last_name",
            "position_type",
            "ref_level",
            "cc_role",
            "nationality",
            "zone",
            "shirt_size",
            "shorts_size",
            "active",
            "type",
        ]
        st.dataframe(
            refs[view_cols].sort_values(["position_type", "last_name", "first_name"]),
            use_container_width=True,
        )

    # Import from Excel/CSV
    st.markdown("---")
    st.subheader("📥 Import referees from Excel / CSV")

    st.markdown(
        """
The file should contain columns (header names):

- `first_name`
- `last_name`
- `gender`
- `nationality`
- `zone`
- `birthdate`
- `fivb_id`
- `email`
- `phone`
- `origin_airport`
- `position_type`
- `cc_role`
- `ref_level`
- `course_year`
- `shirt_size`
- `shorts_size`
- `active` (True/False/Yes/No)
- `type` (Indoor/Beach/Both)

Existing referees will be **kept**.  
New rows will be **added**.  
If an imported row has a FIVB ID that already exists, it will be **skipped**.
"""
    )

    uploaded = st.file_uploader("Upload Excel or CSV file", type=["xlsx", "xls", "csv"], key="ref_import")

    if uploaded is not None:
        try:
            if uploaded.name.lower().endswith(".csv"):
                df_imp = pd.read_csv(uploaded, dtype=str)
            else:
                df_imp = pd.read_excel(uploaded, dtype=str)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            return

        df_imp = df_imp.fillna("")
        st.write("Preview of imported data:")
        st.dataframe(df_imp.head(), use_container_width=True)

        required_cols = ["first_name", "last_name"]
        missing = [c for c in required_cols if c not in df_imp.columns]
        if missing:
            st.error(f"Missing required columns: {missing}")
            return

        if st.button("✅ Import into referee database"):
            refs_current = load_referees()
            existing_fivb = set(refs_current["fivb_id"].astype(str).str.strip())

            new_rows = []
            skipped_duplicate = 0
            added_count = 0

            for _, r in df_imp.iterrows():
                fn = str(r.get("first_name", "")).strip()
                ln = str(r.get("last_name", "")).strip()
                if not fn and not ln:
                    continue

                fivb_str = str(r.get("fivb_id", "")).strip()
                if fivb_str and fivb_str in existing_fivb:
                    skipped_duplicate += 1
                    continue

                gender = str(r.get("gender", "")).strip()
                nationality = str(r.get("nationality", "")).strip()
                zone = str(r.get("zone", "")).strip()
                birthdate = str(r.get("birthdate", "")).strip()
                email = str(r.get("email", "")).strip()
                phone = str(r.get("phone", "")).strip()
                origin_airport = str(r.get("origin_airport", "")).strip()
                position_type = str(r.get("position_type", "")).strip()
                cc_role = str(r.get("cc_role", "")).strip()
                ref_level = str(r.get("ref_level", "")).strip()
                course_year = str(r.get("course_year", "")).strip()
                shirt_size = str(r.get("shirt_size", "")).strip()
                shorts_size = str(r.get("shorts_size", "")).strip()
                active_raw = str(r.get("active", "")).strip().lower()
                ref_type = str(r.get("type", "")).strip()

                if active_raw in ["true", "yes", "y", "1"]:
                    active_str = "True"
                elif active_raw in ["false", "no", "n", "0"]:
                    active_str = "False"
                else:
                    active_str = "True"

                new_rows.append({
                    "ref_id": new_id(),
                    "first_name": fn,
                    "last_name": ln,
                    "gender": gender,
                    "nationality": nationality,
                    "zone": zone,
                    "birthdate": birthdate,
                    "fivb_id": fivb_str,
                    "email": email,
                    "phone": phone,
                    "origin_airport": origin_airport,
                    "position_type": position_type,
                    "cc_role": cc_role,
                    "ref_level": ref_level,
                    "course_year": course_year,
                    "photo_file": "",
                    "passport_file": "",
                    "shirt_size": shirt_size,
                    "shorts_size": shorts_size,
                    "active": active_str,
                    "type": ref_type,
                })
                added_count += 1

            if new_rows:
                df_new = pd.DataFrame(new_rows)
                refs_updated = pd.concat([refs_current, df_new], ignore_index=True)
                save_referees(refs_updated)
                msg = f"Imported {added_count} referees."
                if skipped_duplicate:
                    msg += f" Skipped {skipped_duplicate} rows due to duplicate FIVB IDs."
                st.success(msg)
            else:
                st.info("No new referees were added from this file.")


# =========================
# PAGE: REFEREE SEARCH (PUBLIC)
# =========================

def page_referee_search():
    st.title("🔎 Referee Search & Profile")

    refs = load_referees()
    if refs.empty:
        st.info("No referees in database yet.")
        return

    refs = refs.copy()
    refs["display"] = refs.apply(referee_display_name, axis=1)
    refs = refs.sort_values(["last_name", "first_name"])

    options = []
    mapping = {}
    for _, r in refs.iterrows():
        label = f"{r['first_name']} {r['last_name']} ({r['nationality']})"
        options.append(label)
        mapping[label] = r["ref_id"]

    sel_label = st.selectbox("Select a referee", options)
    sel_id = mapping[sel_label]
    prof = refs[refs["ref_id"] == sel_id].iloc[0]

    colL, colR = st.columns([2, 1])

    with colL:
        st.markdown(f"### {prof['first_name']} {prof['last_name']}")
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

        # PASSPORT – ADMIN ONLY
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


# =========================
# PAGE: ADMIN – EVENTS
# =========================

def page_admin_events():
    require_admin()
    st.title("📅 Admin – Events per Season")

    events = load_events()

    st.markdown("Use this page to **add, edit, or delete events** for each year/season.")

    with st.form("event_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        season = st.text_input("Season", value=str(date.today().year))
    with c2:
        start_date = st.date_input("Start date", value=date.today())
    with c3:
        end_date = st.date_input("End date", value=date.today())

    c4, c5, c6 = st.columns(3)
    with c4:
        location = st.text_input("Location (city/country)", value="")
    with c5:
        ev_name = st.text_input("Event name", value="")
    with c6:
        destination_airport = st.text_input("Destination airport (e.g. BKK, DOH)", value="")

    c7, c8, _ = st.columns(3)
    with c7:
        arrival_date = st.date_input(
            "Arrival date",
            value=start_date,
            help="Recommended arrival date for officials",
        )
    with c8:
        departure_date = st.date_input(
            "Departure date",
            value=end_date,
            help="Recommended departure date for officials",
        )

    requires_availability = st.selectbox(
        "Requires Availability?",
        ["Yes", "No"],
        index=0
    )

    submitted = st.form_submit_button("➕ Add event")

if submitted:
    if not ev_name.strip():
        st.error("Please enter event name.")
    elif end_date < start_date:
        st.error("End date must be on or after the start date.")
    elif departure_date < arrival_date:
        st.error("Departure date must be on or after the arrival date.")
    else:
        new_ev = pd.DataFrame([{
            "event_id": new_id(),
            "season": str(season).strip(),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "event_name": ev_name.strip(),
            "location": location.strip(),
            "destination_airport": destination_airport.strip(),
            "arrival_date": arrival_date.isoformat(),
            "departure_date": departure_date.isoformat(),
            "requires_availability": requires_availability,
        }])
            events = pd.concat([events, new_ev], ignore_index=True)
            save_events(events)
            st.success("Event added ✅")
            st.rerun()

    st.markdown("### Existing events")
    if events.empty:
        st.info("No events yet.")
    else:
        events_disp = events.copy()
        events_disp = events_disp.sort_values(["season", "start_date", "event_name"])
        display_cols = [c for c in events_disp.columns if c != "event_id"]
        st.dataframe(events_disp[display_cols], use_container_width=True)

    if not events.empty:
        st.markdown("---")
        st.subheader("✏️ Edit / 🗑️ Delete event")

        events_sorted = events.sort_values(["season", "start_date", "event_name"])
        labels = []
        id_map = {}
        for _, r in events_sorted.iterrows():
            s = str(r["season"])
            sd = str(r["start_date"])
            ed = str(r["end_date"])
            nm = str(r["event_name"])
            loc = str(r["location"])
            label = f"{s} – {sd} to {ed} – {nm} ({loc})"
            labels.append(label)
            id_map[label] = r["event_id"]

        sel_label = st.selectbox("Select event to edit/delete", ["(None)"] + labels)
        if sel_label != "(None)":
            ev_id = id_map[sel_label]
            ev_row = events[events["event_id"] == ev_id].iloc[0]

            st.markdown("#### Edit event")

with st.form("edit_event_form"):

    c1, c2, c3 = st.columns(3)
    with c1:
        season_edit = st.text_input(
            "Season",
            value=str(ev_row["season"])
        )
    with c2:
        sd_edit = st.date_input(
            "Start date",
            value=_parse_date_str(ev_row["start_date"], date.today())
        )
    with c3:
        ed_edit = st.date_input(
            "End date",
            value=_parse_date_str(ev_row["end_date"], date.today())
        )

    c4, c5, c6 = st.columns(3)
    with c4:
        loc_edit = st.text_input(
            "Location (city/country)",
            value=str(ev_row["location"])
        )
    with c5:
        name_edit = st.text_input(
            "Event name",
            value=str(ev_row["event_name"])
        )
    with c6:
        dest_edit = st.text_input(
            "Destination airport (e.g. BKK, DOH)",
            value=str(ev_row.get("destination_airport", ""))
        )

    c7, c8, c9 = st.columns(3)
    with c7:
        arr_edit = st.date_input(
            "Arrival date",
            value=_parse_date_str(ev_row.get("arrival_date", ""), sd_edit)
        )
    with c8:
        dep_edit = st.date_input(
            "Departure date",
            value=_parse_date_str(ev_row.get("departure_date", ""), ed_edit)
        )
    with c9:
        requires_avail_edit = st.selectbox(
            "Requires Availability?",
            ["Yes", "No"],
            index=["Yes", "No"].index(
                ev_row.get("requires_availability", "Yes") or "Yes"
            )
        )

    save_btn = st.form_submit_button("💾 Save changes")



            if save_btn:
                if not name_edit.strip():
                    st.error("Please enter event name.")
                elif ed_edit < sd_edit:
                    st.error("End date must be on or after start date.")
                elif dep_edit < arr_edit:
                    st.error("Departure date must be on or after arrival date.")
                else:
                    idx = events[events["event_id"] == ev_id].index[0]
                    events.loc[idx, "season"] = str(season_edit).strip()
                    events.loc[idx, "start_date"] = sd_edit.isoformat()
                    events.loc[idx, "end_date"] = ed_edit.isoformat()
                    events.loc[idx, "event_name"] = name_edit.strip()
                    events.loc[idx, "location"] = loc_edit.strip()
                    events.loc[idx, "destination_airport"] = dest_edit.strip()
                    events.loc[idx, "arrival_date"] = arr_edit.isoformat()
			events.loc[idx, "departure_date"] = dep_edit.isoformat()
			events.loc[idx, "requires_availability"] = req_edit


                    save_events(events)
                    st.success("Event updated ✅")
                    st.rerun()

            st.markdown("#### 🗑️ Delete this event")
            st.warning(
                "Deleting this event will also remove all **availability records** and **nominations** linked to it.\n"
                "This action cannot be undone."
            )
            confirm_del = st.checkbox("Yes, delete this event permanently.")
            if st.button("🗑️ Delete event") and confirm_del:
                events = events[events["event_id"] != ev_id]
                save_events(events)

                avail = load_availability()
                if not avail.empty:
                    avail = avail[avail["event_id"] != ev_id]
                    save_availability(avail)

                assignments = load_assignments()
                if not assignments.empty:
                    assignments = assignments[assignments["event_id"] != ev_id]
                    save_assignments(assignments)

                st.success("Event deleted ✅")
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

    # Show only ID, Name (NAT)
    refs_filtered["display"] = refs_filtered.apply(
        lambda r: f"{r['first_name']} {r['last_name']} ({r['nationality']})",
        axis=1
    )

    # =====================================================
    # STEP 2 — REFEREE SELECT
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

    st.markdown(f"### 👋 Hello **{ref_row['first_name']} {ref_row['last_name']}**")

    # =====================================================
    # STEP 3 — SELECT SEASON
    # =====================================================
    season_list = sorted(events["season"].unique())
    st.markdown("### 3️⃣ Choose the season")

    selected_season = st.selectbox("Season", season_list)

    season_events = events[
    (events["season"] == selected_season) &
    (events["requires_availability"].fillna("Yes") == "Yes")
].copy()

    if season_events.empty:
        st.info("No events for this season yet.")
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
    st.markdown(f"### 4️⃣ Availability for **Season {selected_season}**")

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

    if avail.empty and assignments.empty:
        st.info("No availability or nominations yet.")
        return

    seasons_avail = avail["season"].unique().tolist() if not avail.empty else []
    seasons_events = events["season"].unique().tolist() if not events.empty else []
    season_list = sorted(set(seasons_avail + seasons_events))
    if not season_list:
        st.info("No seasons found.")
        return

    selected_season = st.selectbox("Season", season_list)

    avail_season = avail[avail["season"] == str(selected_season)].copy()
    events_season = events[events["season"] == str(selected_season)].copy()

    if avail_season.empty and assignments.empty:
        st.info("No data for this season.")
        return

    refs_small = refs[["ref_id", "first_name", "last_name", "nationality", "zone"]].copy()
    events_small = events_season[["event_id", "season", "event_name", "start_date", "end_date", "location"]].copy()

    if avail_season.empty:
        base = pd.DataFrame(columns=[
            "ref_id",
            "event_id",
            "available",
            "airfare_estimate",
            "timestamp",
            "first_name",
            "last_name",
            "nationality",
            "zone",
            "event_name",
            "start_date",
            "end_date",
            "location",
        ])
    else:
        merged = avail_season.merge(refs_small, on="ref_id", how="left")
        merged = merged.merge(events_small, on=["event_id", "season"], how="left")
        base = merged

    assign_season = assignments.copy()
    if not assign_season.empty:
        assign_season = assign_season.merge(
            events_season[["event_id", "season"]],
            on="event_id",
            how="inner",
        )
        assign_pairs = set(zip(assign_season["ref_id"], assign_season["event_id"]))
    else:
        assign_pairs = set()

    if not assignments.empty and not events_season.empty:
        for _, a in assign_season.iterrows():
            key = (a["ref_id"], a["event_id"])
            if base.empty or not (
                (base["ref_id"] == a["ref_id"]) &
                (base["event_id"] == a["event_id"])
            ).any():
                ref_row = refs_small[refs_small["ref_id"] == a["ref_id"]]
                ev_row = events_small[events_small["event_id"] == a["event_id"]]
                if ref_row.empty or ev_row.empty:
                    continue
                rr = ref_row.iloc[0]
                ee = ev_row.iloc[0]
                new_row = {
                    "ref_id": a["ref_id"],
                    "event_id": a["event_id"],
                    "available": "",
                    "airfare_estimate": "",
                    "timestamp": "",
                    "first_name": rr["first_name"],
                    "last_name": rr["last_name"],
                    "nationality": rr["nationality"],
                    "zone": rr["zone"],
                    "event_name": ee["event_name"],
                    "start_date": ee["start_date"],
                    "end_date": ee["end_date"],
                    "location": ee["location"],
                }
                base = pd.concat([base, pd.DataFrame([new_row])], ignore_index=True)

    if base.empty:
        st.info("No availability or nominations to display.")
        return

    base["ref_name"] = base["first_name"].fillna("") + " " + base["last_name"].fillna("")

    def compute_status(r):
        key = (r["ref_id"], r["event_id"])
        if key in assign_pairs:
            return "Nominated"
        if str(r.get("available", "")).lower() == "true":
            return "Available"
        if str(r.get("available", "")).lower() == "false":
            return "Not available"
        return "Unknown"

    base["status"] = base.apply(compute_status, axis=1)
    base = base.sort_values(["start_date", "event_name", "ref_name"])

    view_cols = [
        "start_date",
        "end_date",
        "event_name",
        "location",
        "ref_name",
        "nationality",
        "zone",
        "status",
        "available",
        "airfare_estimate",
        "timestamp",
    ]

    st.dataframe(base[view_cols], use_container_width=True)


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
                "Referee Search",
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
