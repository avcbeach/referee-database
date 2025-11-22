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

GENDERS = ["", "Male", "Female"]
ZONES = ["", "E", "W", "SEA", "O", "C"]
POSITION_TYPES = ["Control Committee", "Referee"]
CC_ROLES = ["", "Technical Delegate", "Referee Coach", "Both"]
REF_LEVELS = ["", "FIVB", "AVC International", "AVC Candidate", "National"]
REF_TYPES = ["", "Indoor", "Beach", "Both"]
UNIFORM_SIZES = ["", "XS", "S", "M", "L", "XL", "2XL", "3XL"]

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
        # Optional debug
        # st.warning(f"GitHub read error for {path}: {r.status_code}")
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
            # Optional debug:
            # st.warning(f"GitHub write error for {path}: {r_put.status_code}")
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


def load_referees():
    return load_csv(REFEREES_FILE, REFEREE_COLS)


def save_referees(df):
    save_csv(REFEREES_FILE, df)


def load_events():
    df = load_csv(EVENTS_FILE, EVENT_COLS)
    if not df.empty:
        for col in ["start_date", "end_date"]:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date.astype(str)
    return df


def save_events(df):
    save_csv(EVENTS_FILE, df)


def load_availability():
    return load_csv(AVAIL_FILE, AVAIL_COLS)


def save_availability(df):
    save_csv(AVAIL_FILE, df)


def referee_display_name(row):
    return f"{row['first_name']} {row['last_name']}".strip()


# =========================
# PAGE 1: ADMIN – REFEREES
# =========================

def page_admin_referees():
    st.title("👤 Admin – Referees & Officials")

    refs = load_referees()

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
                index=POSITION_TYPES.index(row["position_type"]) if row is not None and row["position_type"] in POSITION_TYPES else 0,
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
            # Shirt size
            shirt_default = row["shirt_size"] if row is not None else ""
            if shirt_default not in UNIFORM_SIZES:
                shirt_default = ""
            shirt_size = st.selectbox(
                "Shirt size",
                UNIFORM_SIZES,
                index=UNIFORM_SIZES.index(shirt_default),
            )
        with c8:
            # Shorts size
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

        # New or update
        if row is None:
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
                # push to GitHub
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
                # push to GitHub
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

    # Delete referee (only when editing an existing person)
    if row is not None:
        st.markdown("---")
        st.subheader("🗑️ Delete this referee")

        ref_name = referee_display_name(row)
        st.warning(
            "You are about to permanently delete **%s**.\n\n"
            "This will remove:\n"
            "- Their personal details\n"
            "- All availability submissions linked to this referee\n\n"
            "This action cannot be undone." % ref_name
        )

        confirm_delete = st.checkbox("Yes, I want to delete this referee permanently.")

        if st.button("🗑️ Delete Referee") and confirm_delete:
            # Remove from referees list
            refs = refs[refs["ref_id"] != row["ref_id"]]

            # Remove all availability records for this referee
            avail = load_availability()
            if not avail.empty:
                avail = avail[avail["ref_id"] != row["ref_id"]]
                save_availability(avail)

            # Remove local files (we leave GitHub files as archive for safety)
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


# =========================
# PAGE 2: ADMIN – EVENTS
# =========================

def page_admin_events():
    st.title("📅 Admin – Events per Season")

    events = load_events()

    st.markdown("Use this page to **add events** for each year/season.")

    with st.form("event_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            season = st.text_input("Season", value=str(date.today().year))
        with c2:
            start_date = st.date_input("Start date", value=date.today())
        with c3:
            end_date = st.date_input("End date", value=date.today())

        location = st.text_input("Location (city/country)", value="")
        ev_name = st.text_input("Event name", value="")
        submitted = st.form_submit_button("➕ Add event")

    if submitted:
        if not ev_name.strip():
            st.error("Please enter event name.")
        elif end_date < start_date:
            st.error("End date must be on or after the start date.")
        else:
            new_ev = pd.DataFrame([{
                "event_id": new_id(),
                "season": str(season).strip(),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "event_name": ev_name.strip(),
                "location": location.strip(),
            }])
            events = pd.concat([events, new_ev], ignore_index=True)
            save_events(events)
            st.success("Event added ✅")

    st.markdown("### Existing events")
    if events.empty:
        st.info("No events yet.")
    else:
        events_disp = events.copy()
        events_disp = events_disp.sort_values(["season", "start_date", "event_name"])
        st.dataframe(events_disp, use_container_width=True)


# =========================
# PAGE 3: REFEREE AVAILABILITY FORM
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
Please select your name, choose the season, and tick which events you are available for.  
You may also provide a **tentative airfare estimate** from your origin airport to the event country.

For flight options you can check:  
[Trip.com – Flights](https://www.trip.com/flights/)
"""
    )

    refs["display"] = refs.apply(referee_display_name, axis=1)
    refs = refs.sort_values("display")

    ref_label = st.selectbox("Your name", refs["display"].tolist())
    season_list = sorted(events["season"].unique())
    selected_season = st.selectbox("Season", season_list)

    ref_row = refs[refs["display"] == ref_label].iloc[0]
    ref_id = ref_row["ref_id"]

    season_events = events[events["season"] == selected_season].copy()
    if season_events.empty:
        st.info("No events for this season yet.")
        return

    # Merge existing availability (if any)
    avail_ref = avail[(avail["ref_id"] == ref_id) & (avail["season"] == str(selected_season))]
    avail_ref = avail_ref.set_index("event_id") if not avail_ref.empty else pd.DataFrame()

    # Build editable table
    display_df = season_events[["event_id", "start_date", "end_date", "event_name", "location"]].copy()
    display_df["available"] = False
    display_df["airfare_estimate"] = ""

    for i, r in display_df.iterrows():
        ev_id = r["event_id"]
        if not avail_ref.empty and ev_id in avail_ref.index:
            display_df.at[i, "available"] = (avail_ref.loc[ev_id]["available"] == "True")
            display_df.at[i, "airfare_estimate"] = avail_ref.loc[ev_id]["airfare_estimate"]

    # Show editor
    st.markdown("### Your availability for events in this season")
    edited = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "available": st.column_config.CheckboxColumn("Available"),
            "airfare_estimate": st.column_config.TextColumn("Airfare estimate (e.g. 500 USD)"),
        },
        disabled=["event_id", "start_date", "end_date", "event_name", "location"],
    )

    if st.button("📨 Submit availability"):
        # Clear old availability for this ref & season
        avail = avail[~((avail["ref_id"] == ref_id) & (avail["season"] == str(selected_season)))]

        # Insert new
        new_rows = []
        now_str = datetime.utcnow().isoformat()

        for _, r in edited.iterrows():
            available = bool(r["available"])
            airfare = str(r["airfare_estimate"]).strip()
            ev_id = r["event_id"]
            new_rows.append({
                "avail_id": new_id(),
                "ref_id": ref_id,
                "season": str(selected_season),
                "event_id": ev_id,
                "available": str(available),
                "airfare_estimate": airfare,
                "timestamp": now_str,
            })

        if new_rows:
            avail = pd.concat([avail, pd.DataFrame(new_rows)], ignore_index=True)

        save_availability(avail)
        st.success("Thank you! Your availability has been recorded. ✅")


# =========================
# PAGE 4: ADMIN – VIEW AVAILABILITY
# =========================

def page_admin_availability():
    st.title("📊 Admin – Availability Overview")

    refs = load_referees()
    events = load_events()
    avail = load_availability()

    if avail.empty:
        st.info("No availability submissions yet.")
        return

    season_list = sorted(avail["season"].unique())
    selected_season = st.selectbox("Season", season_list)

    avail_season = avail[avail["season"] == selected_season].copy()
    if avail_season.empty:
        st.info("No availability in this season.")
        return

    # Join with refs and events
    refs_small = refs[["ref_id", "first_name", "last_name", "nationality", "zone"]].copy()
    events_small = events[["event_id", "season", "event_name", "start_date", "end_date", "location"]].copy()

    merged = avail_season.merge(refs_small, on="ref_id", how="left")
    merged = merged.merge(events_small, on=["event_id", "season"], how="left")

    merged["ref_name"] = merged["first_name"].fillna("") + " " + merged["last_name"].fillna("")
    merged = merged.sort_values(["start_date", "event_name", "ref_name"])

    view_cols = [
        "start_date",
        "end_date",
        "event_name",
        "location",
        "ref_name",
        "nationality",
        "zone",
        "available",
        "airfare_estimate",
        "timestamp",
    ]

    st.dataframe(merged[view_cols], use_container_width=True)


# =========================
# MAIN
# =========================

def main():
    st.sidebar.title("🏖️ Beach Referee DB")

    page = st.sidebar.radio(
        "Go to",
        [
            "Admin – Referees",
            "Admin – Events",
            "Referee Availability Form",
            "Admin – View Availability",
        ],
    )

    if page == "Admin – Referees":
        page_admin_referees()
    elif page == "Admin – Events":
        page_admin_events()
    elif page == "Referee Availability Form":
        page_availability_form()
    elif page == "Admin – View Availability":
        page_admin_availability()


if __name__ == "__main__":
    main()
