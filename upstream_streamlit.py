"""
upstream_streamlit.py
=====================
Streamlit web UI for pushing customer records to the data-entry REST API.

Run:
    streamlit run upstream_streamlit.py

Requirements:
    pip install streamlit requests
"""

import csv
import io
import requests
import streamlit as st

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Upstream Data Uploader",
    page_icon="📤",
    layout="wide",
)

st.title("📤 Upstream Data Uploader")
st.caption("Push customer records to the data-entry REST API")

# ─── API Configuration ────────────────────────────────────────────────────────
with st.expander("⚙️ API Configuration", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        base_url = st.text_input("Base URL", value="http://localhost:5000")
    with col2:
        api_key = st.text_input("API Key", value="upstream-app-key-001", type="password")

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": api_key,
}

# ─── API helper ───────────────────────────────────────────────────────────────
def push_customer(customer: dict) -> dict:
    response = requests.post(
        f"{base_url.rstrip('/')}/api/customers",
        json=customer,
        headers=HEADERS,
        timeout=10,
    )
    if response.status_code == 201:
        return response.json()
    raise RuntimeError(f"HTTP {response.status_code}: {response.text}")

# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab_single, tab_csv = st.tabs(["📝 Single Record", "📂 CSV Batch Upload"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 – Single Record
# ══════════════════════════════════════════════════════════════════════════════
with tab_single:
    st.subheader("Enter Customer Details")

    col1, col2 = st.columns(2)
    with col1:
        first_name = st.text_input("First Name *")
        road       = st.text_input("Road / Street *")
        state      = st.text_input("State *")
        country    = st.text_input("Country *", value="USA")
        dob        = st.text_input("Date of Birth (MM/DD/YYYY) *", placeholder="03/15/1985")
    with col2:
        last_name  = st.text_input("Last Name *")
        city       = st.text_input("City *")
        zip_code   = st.text_input("ZIP Code *")
        phone      = st.text_input("Phone *", placeholder="6171234567")

    st.markdown("---")
    if st.button("🚀 Submit Record", type="primary", use_container_width=False):
        customer = {
            "first_name": first_name.strip(),
            "last_name":  last_name.strip(),
            "road":       road.strip(),
            "city":       city.strip(),
            "state":      state.strip(),
            "zip":        zip_code.strip(),
            "country":    country.strip(),
            "phone":      phone.strip(),
            "dob":        dob.strip(),
        }
        missing = [k for k, v in customer.items() if not v]
        if missing:
            st.error(f"Please fill in: {', '.join(missing)}")
        else:
            with st.spinner("Submitting…"):
                try:
                    created = push_customer(customer)
                    st.success(
                        f"✅ Customer created!\n\n"
                        f"**ID:** {created['id']}  \n"
                        f"**Name:** {created['first_name']} {created['last_name']}"
                    )
                except Exception as exc:
                    st.error(f"❌ {exc}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 – CSV Batch Upload
# ══════════════════════════════════════════════════════════════════════════════
REQUIRED_COLS = ["first_name", "last_name", "road", "city",
                 "state", "zip", "country", "phone", "dob"]

with tab_csv:
    st.subheader("Upload CSV File")
    st.caption("Required columns: " + ", ".join(REQUIRED_COLS))

    uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])

    if uploaded_file:
        try:
            content = uploaded_file.read().decode("utf-8-sig")
            reader  = csv.DictReader(io.StringIO(content))
            rows    = list(reader)
        except Exception as exc:
            st.error(f"Could not read file: {exc}")
            rows = []

        if rows:
            missing_cols = [c for c in REQUIRED_COLS if c not in rows[0]]
            if missing_cols:
                st.warning(f"⚠️ Missing columns: {', '.join(missing_cols)}")

            # Normalise rows
            data = [{col: row.get(col, "").strip() for col in REQUIRED_COLS}
                    for row in rows]

            st.markdown(f"**{len(data)} record(s) loaded.** Preview (first 5 rows):")
            st.dataframe(data[:5], use_container_width=True)

            st.markdown("---")
            if st.button("🚀 Push All Records", type="primary", use_container_width=False):
                progress = st.progress(0, text="Starting…")
                log_area = st.empty()
                log_lines = []
                ok_count  = 0

                for i, customer in enumerate(data, start=1):
                    name = f"{customer['first_name']} {customer['last_name']}"
                    try:
                        created = push_customer(customer)
                        log_lines.append(
                            f"✅ [{i}/{len(data)}] Created id={created['id']}  {name}")
                        ok_count += 1
                    except RuntimeError as exc:
                        log_lines.append(f"❌ [{i}/{len(data)}] Failed – {name}: {exc}")

                    progress.progress(i / len(data),
                                      text=f"Processing {i}/{len(data)}…")
                    log_area.code("\n".join(log_lines), language=None)

                progress.empty()
                if ok_count == len(data):
                    st.success(f"🎉 All {ok_count} records pushed successfully!")
                else:
                    st.warning(
                        f"⚠️ {ok_count}/{len(data)} records pushed. "
                        f"Check the log above for failures.")
        else:
            st.warning("The CSV file contains no data rows.")
    else:
        st.info("Upload a CSV file to get started.")

        # Download a sample CSV template
        sample_csv = (
            "first_name,last_name,road,city,state,zip,country,phone,dob\n"
            "Alice,Johnson,10 Elm Street,Boston,MA,02101,USA,6171234567,03/15/1985\n"
            "Bob,Williams,55 Oak Avenue,Chicago,IL,60601,USA,3129876543,07/22/1990\n"
        )
        st.download_button(
            label="⬇️ Download sample CSV template",
            data=sample_csv,
            file_name="sample_customers.csv",
            mime="text/csv",
        )
