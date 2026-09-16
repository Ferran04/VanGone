# VanGone

A two-script pipeline that scrapes the Van Gogh Museum's online collection and downloads the
highest-resolution image available for every artwork.

## How it works

1. **`getVanGoghIDs.py`** — drives headless Firefox (Selenium) against the museum's collection
   search page, scrolls until all results are loaded, then parses the page with BeautifulSoup to
   collect each artwork's id and title. Writes `vangogh_artwork_ids.csv`.
2. **`VanGone.py`** — reads `vangogh_artwork_ids.csv`, fetches each artwork's page, extracts its
   IIIF image URL, and downloads the maximum-resolution version into `VanGones/` as
   `{title}_{id}.jpg`. Downloads run concurrently, skip files already downloaded, and can be
   stopped safely with Ctrl+C.

## Requirements

- Python 3
- Firefox (for Selenium; geckodriver is fetched automatically via `webdriver-manager`)
- `pip install -r requirements.txt`

## Usage

```
python getVanGoghIDs.py   # scrapes the collection site -> vangogh_artwork_ids.csv
python VanGone.py         # downloads images -> VanGones/
```

## Output

- `vangogh_artwork_ids.csv` — scraped id/title list.
- `VanGones/` — downloaded images, plus `downloader.log` and `download_log.json` (a record of
  successful downloads).
