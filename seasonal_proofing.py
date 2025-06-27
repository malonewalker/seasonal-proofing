import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from time import sleep
from datetime import datetime
from io import BytesIO
import urllib3

# Disable SSL certificate warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.title("📄 Best Pick Reports Scraper")

# --- Upload file ---
uploaded_file = st.file_uploader("Upload a CSV or Excel file with a column named 'URL'", type=["csv", "xlsx"])

if uploaded_file:
    # Read the file
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    if "URL" not in df.columns:
        st.error("❌ File must contain a column named 'URL'")
        st.stop()

    urls = df["URL"].dropna().unique().tolist()

    st.success(f"Loaded {len(urls)} unique URLs.")
    st.write("Scraping company names, years, and order...")

    # --- Final working scraper function ---
    def scrape_category_page(url):
        try:
            res = requests.get(url, timeout=15, verify=False)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")
            companies = []

            cards = soup.find_all("div", class_="provider-summary")
            if not cards:
                print(f"[DEBUG] No provider-summary elements found on {url}")

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
                    companies.append({
                        "Category URL": url,
                        "Company Name": name_tag.get_text(strip=True),
                        "Years as Best Pick": years_text,
                        "Position on Page": idx + 1
                    })

            return companies

        except Exception as e:
            return [{
                "Category URL": url,
                "Company Name": "ERROR",
                "Years as Best Pick": f"Error: {str(e)}",
                "Position on Page": None
            }]

    # --- Scrape all URLs ---
    all_results = []
    progress = st.progress(0)

    for i, url in enumerate(urls):
        results =
