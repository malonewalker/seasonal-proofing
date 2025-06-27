import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
from time import sleep
from datetime import datetime
from io import BytesIO
import os

st.title("🕵️‍♂️ Best Pick Reports Scraper (Selenium)")

uploaded_file = st.file_uploader("Upload CSV or Excel with a column named 'URL'", type=["csv", "xlsx"])

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    if "URL" not in df.columns:
        st.error("Your file must contain a column named 'URL'")
        st.stop()

    urls = df["URL"].dropna().unique().tolist()
    st.success(f"Loaded {len(urls)} URLs.")

    # --- Setup Chrome headless driver ---
    def get_driver():
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # Auto-detect or customize path to chromedriver
        service = Service()  # You can use: Service("/path/to/chromedriver")
        return webdriver.Chrome(service=service, options=chrome_options)

    # --- Scraper Function ---
    def scrape_with_selenium(url, driver):
        driver.get(url)
        sleep(3)  # wait for JS to load
        soup = BeautifulSoup(driver.page_source, "html.parser")
        companies = []

        cards = soup.find_all("div", class_="provider-summary")
        for idx, card in enumerate(cards):
            link = card.find("a", class_="provider-link")
            if not link:
                continue

            name_tag = link.find("h3", class_="provider-name")
            badge_tag = link.find("div", class_="badge")
            years_text = ""
            if badge_tag and badge_tag.find("span"):
                years_text = badge_tag.find("span").get_text(strip=True)

            if name_tag:
                companies.append({
                    "Category URL": url,
                    "Company Name": name_tag.get_text(strip=True),
                    "Years as Best Pick": years_text,
                    "Position on Page": idx + 1
                })

        return companies

    # --- Run Scraping ---
    all_results = []
    driver = get_driver()
    progress = st.progress(0)

    for i, url in enumerate(urls):
        st.write(f"Scraping: {url}")
        companies = scrape_with_selenium(url, driver)
        all_results.extend(companies)
        progress.progress((i + 1) / len(urls))
        sleep(1)

    driver.quit()

    # --- Show and Save Output ---
    results_df = pd.DataFrame(all_results)
    st.subheader("✅ Scraped Results")
    st.dataframe(results_df)

    towrite = BytesIO()
    results_df.to_excel(towrite, index=False, engine="openpyxl")
    towrite.seek(0)

    st.download_button(
        label="📥 Download Excel",
        data=towrite,
        file_name=f"scraped_bestpicks_{datetime.today().date()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
