import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st
import time
from datetime import datetime
from io import BytesIO
import urllib3

st.title("🔒 Best Pick Reports Seasonal Web Proofing")

PASSWORD = "BPRFSR"
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    password_input = st.text_input("Enter password to continue:", type="password")
    if password_input == PASSWORD:
        st.session_state.authenticated = True
        st.success("✅ Password correct. You are now logged in.")
        st.stop()
    elif password_input:
        st.error("❌ Incorrect password.")
        st.stop()

# --- File Upload ---
uploaded_file = st.file_uploader("Upload the Best Pick CSV file", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.success("File uploaded and loaded!")

    # Disable SSL warnings
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # --- Clean & Prepare ---
    def extract_category_url(url):
        parts = str(url).strip().split("/")
        if len(parts) >= 6:
            return "/".join(parts[:5])  # e.g. https://www.bestpickreports.com/appliance-repair/atlanta
        return None

    df["Category URL"] = df["Company Web Profile URL"].apply(extract_category_url)
    df["Oldest Signing Date"] = pd.to_datetime(df["Oldest Signing Date"], errors="coerce")

    valid_df = df.dropna(subset=["Category URL"])
    category_urls = valid_df["Category URL"].drop_duplicates().tolist()

    expected = (
        valid_df.sort_values(["Category URL", "Oldest Signing Date"])
                .groupby("Category URL")
                .apply(lambda x: x.reset_index(drop=True))
                .reset_index(drop=True)
    )

    # --- Scraper Function ---
    def extract_companies_from_page(url):
        try:
            res = requests.get(url, timeout=15, verify=False)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")
            companies = []

            for idx, card in enumerate(soup.select(".provider-summary")):
                name_tag = card.find(class_="provider-name")
                years_tag = card.find(class_="years") or card.find(class_="badge")

                if name_tag:
                    companies.append({
                        "name": name_tag.get_text(strip=True),
                        "years_text": years_tag.get_text(strip=True) if years_tag else "",
                        "position": idx + 1
                    })
            return companies
        except Exception as e:
            return [{"error": str(e)}]

    # --- Validation ---
    results = []
    progress_bar = st.progress(0)
    progress_step = 1 / len(category_urls)

    for i, cat_url in enumerate(category_urls):
        scraped = extract_companies_from_page(cat_url)
        time.sleep(1.0)  # One request per second

        expected_companies = expected[expected["Category URL"] == cat_url]
        issues = []

        if scraped and "error" in scraped[0]:
            issues.append(f"ERROR: {scraped[0]['error']}")
        else:
            actual_names = [c["name"].strip().lower() for c in scraped]
            expected_names = expected_companies["PublishedName"].str.strip().str.lower().tolist()

            # 1. Unexpected companies on page
            for name in actual_names:
                if name not in expected_names:
                    issues.append(f"Unexpected company on page: {name}")

            # 2. Missing companies from page
            for name in expected_names:
                if name not in actual_names:
                    issues.append(f"Missing company from page: {name}")

            # 3. Validate order and years
            for expected_idx, row in expected_companies.iterrows():
                expected_name = row["PublishedName"].strip().lower()
                expected_years = str(row["OldestBestPickText"]).strip()

                # Find actual scraped record
                matches = [c for c in scraped if c["name"].strip().lower() == expected_name]
                if matches:
                    actual = matches[0]
                    actual_position = actual["position"]
                    expected_position = expected_companies.index.get_loc(expected_idx) + 1
                    if actual_position != expected_position:
                        issues.append(f"Wrong order: {expected_name} (expected {expected_position}, found {actual_position})")
                    if expected_years not in actual["years_text"]:
                        issues.append(f"Wrong years: {expected_name} - Expected '{expected_years}' but found '{actual['years_text']}'")

        if issues:
            results.append({
                "Category URL": cat_url,
                "Errors": "; ".join(issues)
            })

        progress_bar.progress(min((i + 1) * progress_step, 1.0))

    # --- Show Only Errors ---
    if results:
        results_df = pd.DataFrame(results)

        st.subheader("❌ Errors Found")
        st.dataframe(results_df)

        towrite = BytesIO()
        results_df.to_csv(towrite, index=False)
        towrite.seek(0)

        st.download_button(
            label="Download Errors as CSV",
            data=towrite,
            file_name=f"bestpick_validation_errors_{datetime.today().date()}.csv",
            mime="text/csv"
        )
    else:
        st.success("✅ All categories passed validation. No errors found.")
