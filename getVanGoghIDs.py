from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.options import Options
from bs4 import BeautifulSoup
import time
import re
import csv

# Setup Selenium in headless mode
options = Options()
options.headless = True  # Run in headless mode (no window)
driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()), options=options)

# Go to the Van Gogh collection page
driver.get("https://www.vangoghmuseum.nl/en/collection?q=&Artist=Vincent+van+Gogh")

# Scroll until no more content is loaded
SCROLL_PAUSE = 3.5
last_height = driver.execute_script("return document.body.scrollHeight")

while True:
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(SCROLL_PAUSE)
    new_height = driver.execute_script("return document.body.scrollHeight")
    if new_height == last_height:
        break
    last_height = new_height

# Parse the final loaded HTML
soup = BeautifulSoup(driver.page_source, 'html.parser')
driver.quit()

artworks = []
seen_ids = set()

for article in soup.select(".collection-art-object-list-item a"):
    href = article.get("href", "")
    title = article.get("title", "").strip()

    if not href.startswith("/en/collection/"):
        continue

    base_id = href.split("/")[-1]

    # Handle recto/verso
    if "(recto)" in title.lower() or "(verso)" in title.lower():
        id_r = f"{base_id}r"
        id_v = f"{base_id}v"
        artworks.append((id_r, title.replace("(recto)", "").replace("(verso)", "").strip()))
        artworks.append((id_v, title.replace("(recto)", "").replace("(verso)", "").strip()))
        seen_ids.update([id_r, id_v])
    else:
        if base_id not in seen_ids:
            artworks.append((base_id, title))
            seen_ids.add(base_id)

# Save to CSV file
with open("vangogh_artwork_ids.csv", "w", encoding="utf-8", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["id", "title"])  # header row
    for art_id, title in artworks:
        safe_title = re.sub(r'[\\/*?:"<>|]', "", title)  # clean filename chars if needed
        writer.writerow([art_id, safe_title])
        print(f"{art_id} - {safe_title}")
