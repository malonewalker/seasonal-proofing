import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from time import sleep
from datetime import datetime
from io import BytesIO
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.title("🔍 Best Pick Reports Category Scraper")

# --- Upload File ---
uploaded_file = st.file_uploader("Upload a CSV or Excel file with a column named 'URL'", type=["csv", "xlsx"])

if uploaded_file:
    # --- Load Data ---
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    if "URL" not in df.columns:
        st.error("❌ Your file must contain a column named 'URL'")
        st.stop()

    urls = df["URL"].dropna().unique().tolist()
    st.success(f"✅ Loaded {len(urls)} unique URLs.")

    # --- Scraper Function with Debug Logging ---
    def scrape_category_page(url):
        st.write(f"🔍 Scraping: {url}")
        try:
            res = requests.get(url, timeout=15, verify=False)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")
            companies = []

            cards = soup.find_all("div", class_="provider-summary")
            st.write(f"➡️ Found {len(cards)} company cards.")

            for idx, card in enumerate(cards):
                link = card.find("a", class_="provider-link")
                if not link:
                    continue

                name_tag = link.find("h3", class_="provider-name")
                badge_tag = link.find("div", class_="badge")
                years_text = ""

                if badge_tag:
                    span = badge_tag.find("span")
                    if span:
                        years_text = span.get_text(strip=True)

                if name_tag:
                    company = {
                        "Category URL": url,
                        "Company Name": name_tag.get_text(strip=True),
                        "Years as Best Pick": years_text,
                        "Position on Page": idx + 1
                    }
                    st.write(company)
                    companies.append(company)

            return companies

        except Exception as e:
            st.error(f"❌ Error scraping {url}: {e}")
            return [{
                "Category URL": url,
                "Company Name": "ERROR",
                "Years as Best Pick": f"Error: {str(e)}",
                "Position on Page": None
            }]

    # --- Run Scraping ---
    all_results = []
    progress = st.progress(0)

    for i, url in enumerate(urls):
        results = scrape_category_page(url)
        all_results.extend(results)
        progress.progress((i + 1) / len(urls))
        sleep(1)

    results_df = pd.DataFrame(all_results)

    # --- Show Output ---
    st.subheader("📊 Scraped Results")
    st.dataframe(results_df)

    # --- Export Excel ---
    towrite = BytesIO()
    results_df.to_excel(towrite, index=False, engine="openpyxl")
    towrite.seek(0)

    st.download_button(
        label="📥 Download Excel",
        data=towrite,
        file_name=f"scraped_bestpicks_{datetime.today().date()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
