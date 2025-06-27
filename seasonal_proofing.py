import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st
import time
from datetime import datetime
from io import BytesIO
import urllib3

# --- Streamlit UI ---
st.title("Best Pick Reports Seasonal Web Proofing")

uploaded_file = st.file_uploader("Upload the Best Pick CSV file", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.success("File uploaded and loaded!")

    # --- Disable SSL warnings for environments with untrusted certs ---
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # --- Category URL Extraction ---
    def extract_category_url(url):
        parts = str(url).strip().split("/")
        if len(parts) >= 6:
            return "/".join(parts[:5])  # https://www.bestpickreports.com/category/city
        return None

    df["Category URL"] = df["Company Web Profile URL"].apply(extract_category_url)
    df["Oldest Signing Date"] = pd.to_datetime(df["Oldest Signing Date"], errors="coerce")

    valid_df = df.dropna(subset=["Category URL"])
    category_urls = valid_df["Category URL"].drop_duplicates().tolist()

    # Expected DataFrame sorted by Category and Oldest Signing Date
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

            for card in soup.select(".provider-summary, .company-card"):
                name = card.find("h3")
                badge = card.find(class_="years") or card.find(class_="badge")
                if name:
                    companies.append({
                        "name": name.get_text(strip=True),
                        "years_text": badge.get_text(strip=True) if badge else ""
                    })
            return companies
        except Exception as e:
            return [{"error": str(e)}]

    # --- Progress Tracker ---
    results = []
    progress_bar = st.progress(0)
    progress_step = 1 / len(category_urls)

    for i, cat_url in enumerate(category_urls):
        scraped = extract_companies_from_page(cat_url)
        time.sleep(1.0)  # Limit: 1 request per second

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

            # 3. Check order and year badge
            filtered_scraped = [c for c in scraped if c["name"].strip().lower() in expected_names]

            for idx, actual in enumerate(filtered_scraped):
                name = actual["name"].strip().lower()
                match = expected_companies[
                    expected_companies["PublishedName"].str.strip().str.lower() == name
                ]
                if not match.empty:
                    expected_idx = match.index[0] - expected_companies.index.min()
                    if expected_idx != idx:
                        issues.append(
                            f"Wrong order: {name} (expected {expected_idx + 1}, found {idx + 1})"
                        )

                    expected_years = str(match["OldestBestPickText"].values[0]).strip()
                    if expected_years not in actual["years_text"]:
                        issues.append(
                            f"Wrong years: {name} - Expected '{expected_years}' but found '{actual['years_text']}'"
                        )

        if issues:
            results.append({
                "Category URL": cat_url,
                "Errors": "; ".join(issues)
            })

        progress_bar.progress(min((i + 1) * progress_step, 1.0))

    # --- Results ---
    if results:
        results_df = pd.DataFrame(results)

        st.subheader("❌ Errors Found in the Following Categories")
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
