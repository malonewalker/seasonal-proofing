import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st
from io import BytesIO
from datetime import datetime
import time

# --- Load Excel ---
st.title("Best Pick Reports Seasonal Web Proofing")

uploaded_file = st.file_uploader("Upload the Best Pick Excel file", type=["csv", "xlsx"])

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.success("File uploaded and loaded!")

    # --- Toggle and Slider for Rate Limiting ---
    enable_rate_limit = st.checkbox("Enable rate limiting between requests", value=True)

    if enable_rate_limit:
        rate_limit = st.slider(
            "Delay between requests (seconds)",
            min_value=0.0,
            max_value=5.0,
            value=1.0,
            step=0.1
        )
    else:
        rate_limit = 0.0

    # --- Preprocess ---
    df["Category URL"] = df["Company Web Profile URL"].apply(lambda x: "/".join(str(x).split("/")[:5]))
    df["Oldest Signing Date"] = pd.to_datetime(df["Oldest Signing Date"], errors="coerce")

    expected = (
        df.sort_values("Oldest Signing Date")
          .groupby("Category URL")
          .apply(lambda x: x.reset_index(drop=True))
          .reset_index(drop=True)
    )

    category_urls = expected["Category URL"].dropna().unique()

    # --- Scraper ---
    def extract_companies_from_page(url):
        try:
            res = requests.get(url, timeout=10)
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

    results = []

    with st.spinner("Scraping category pages..."):
        for cat_url in category_urls:
            scraped = extract_companies_from_page(cat_url)
            time.sleep(rate_limit)  # Delay applied based on toggle/slider

            expected_companies = expected[expected["Category URL"] == cat_url]
            issues = []

            for i, actual in enumerate(scraped):
                if "error" in actual:
                    issues.append(f"ERROR: {actual['error']}")
                    continue
                name = actual["name"]
                match = expected_companies[
                    expected_companies["PublishedName"].str.strip().str.lower() == name.strip().lower()
                ]

                if match.empty:
                    issues.append(f"Unexpected company: {name}")
                else:
                    idx_expected = match.index[0] - expected_companies.index.min()
                    if idx_expected != i:
                        issues.append(
                            f"Wrong order: {name} (expected position {idx_expected + 1}, found {i + 1})"
                        )
                    expected_years = str(match["OldestBestPickText"].values[0]).strip()
                    if expected_years not in actual["years_text"]:
                        issues.append(
                            f"Wrong years: {name} - Expected '{expected_years}' but found '{actual['years_text']}'"
                        )

            results.append({
                "Category URL": cat_url,
                "Errors": "; ".join(issues) if issues else "No issues"
            })

    results_df = pd.DataFrame(results)

    # --- Dashboard ---
    st.subheader("Validation Results by Category")
    st.dataframe(results_df)

    # Summary stats
    total_categories = len(results_df)
    error_categories = results_df[results_df["Errors"] != "No issues"]
    no_error_count = total_categories - len(error_categories)

    st.metric("Total Categories", total_categories)
    st.metric("Categories With Errors", len(error_categories))
    st.metric("Categories With No Errors", no_error_count)
    st.metric("Total Errors", error_categories["Errors"].str.count(";").sum())

    # --- Export ---
    towrite = BytesIO()
    results_df.to_excel(towrite, index=False, engine='openpyxl')
    towrite.seek(0)

    st.download_button(
        label="Download results as Excel",
        data=towrite,
        file_name=f"bestpick_validation_{datetime.today().date()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
