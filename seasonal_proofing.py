import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from time import sleep

from playwright.sync_api import sync_playwright

st.title("🕵️‍♀️ Best Pick Reports Scraper (Playwright)")

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

    def scrape_page_with_playwright(url):
        companies = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url)
            page.wait_for_timeout(3000)  # wait for JS to load

            cards = page.query_selector_all(".provider-summary")
            for idx, card in enumerate(cards):
                name = card.query_selector("h3.provider-name")
                badge = card.query_selector("div.badge span")
                if name:
                    companies.append({
                        "Category URL": url,
                        "Company Name": name.inner_text().strip(),
                        "Years as Best Pick": badge.inner_text().strip() if badge else "",
                        "Position on Page": idx + 1
                    })

            browser.close()
        return companies

    all_results = []
    progress = st.progress(0)

    for i, url in enumerate(urls):
        st.write(f"Scraping: {url}")
        companies = scrape_page_with_playwright(url)
        all_results.extend(companies)
        progress.progress((i + 1) / len(urls))
        sleep(1)

    results_df = pd.DataFrame(all_results)

    st.subheader("✅ Scraped Results")
    st.dataframe(results_df)

    towrite = BytesIO()
    results_df.to_excel(towrite, index=False, engine="openpyxl")
    towrite.seek(0)

    st.download_button(
        label="📥 Download Results as Excel",
        data=towrite,
        file_name=f"scraped_bestpicks_{datetime.today().date()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
