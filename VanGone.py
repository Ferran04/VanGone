import csv
import requests
from bs4 import BeautifulSoup
import re
import os
import time
from concurrent.futures import ThreadPoolExecutor
import logging
from tqdm import tqdm
import json
from datetime import datetime
import threading
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed

download_log = []
log_lock = threading.Lock()

stop_requested = False

def signal_handler(sig, frame):
    global stop_requested
    logging.info("Shutdown signal received, stopping new downloads...")
    stop_requested = True

# Register the handler for SIGINT (Ctrl+C)
signal.signal(signal.SIGINT, signal_handler)

def log_success(art_id, title, filepath):
    entry = {
        "id": art_id,
        "title": title,
        "filepath": filepath,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    with log_lock:
        download_log.append(entry)

def save_log_to_file(log_path="VanGones/download_log.json"):
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(download_log, f, indent=2)

# Configure logging
logging.basicConfig(
    filename='VanGones/downloader.log',
    filemode='a',
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)

# Optional: Also log to console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('[%(levelname)s] %(message)s')
console.setFormatter(formatter)
logging.getLogger().addHandler(console)

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

def get_iiif_base_url(session, artwork_id):
    url = f"https://www.vangoghmuseum.nl/en/collection/{artwork_id}"
    try:
        r = session.get(url, timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"[{artwork_id}] Request failed: {e}")
        return None

    try:
        soup = BeautifulSoup(r.text, 'html.parser')
        container = soup.select_one(".art-object-header-image.object-fit-container.contain img.lazy-image")
        if not container:
            logging.warning(f"No image found on page for {artwork_id}")
            return None

        # Get data-src or src
        iiif_url = container.get("data-src") or container.get("src")
        if not iiif_url:
            logging.warning(f"No IIIF URL found for {artwork_id}")
            return None

        # Example iiif_url:
        # https://iiif.micr.io/hfWsc/full/600,/0/default.jpg
        # We want the base URL: https://iiif.micr.io/hfWsc
        parts = iiif_url.split('/')
        # The base should be first 4 parts: https:, '', iiif.micr.io, hfWsc
        base_url = "/".join(parts[:4])
        return base_url
    except Exception as e:
        logging.exception(f"[{artwork_id}] Failed to parse IIIF URL: {e}")
        return None


def download_max_resolution_image(session, base_url, save_path, art_id=None, title=None, retries=3, backoff=2):
    max_url = f"{base_url}/full/max/0/default.jpg"
    attempt = 0

    while attempt < retries:
        logging.info(f"Downloading {max_url} (Attempt {attempt + 1}/{retries})")
        try:
            r = session.get(max_url, stream=True, timeout=10)
            r.raise_for_status()
            if r.status_code == 200:
                with open(save_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                logging.info(f"Saved image to {save_path}")
                if art_id and title:
                    log_success(art_id, title, save_path)
                return True
            else:
                logging.warning(f"Failed to download image (status code {r.status_code})")
        except requests.RequestException as e:
            logging.error(f"Error during download: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error saving image {save_path}: {e}")
            break  # don't retry non-network errors

        attempt += 1
        sleep_time = backoff ** attempt
        logging.info(f"Retrying in {sleep_time} seconds...")
        time.sleep(sleep_time)

    logging.warning(f"Failed to download image after {retries} attempts.")
    return False

thread_local = threading.local()

def get_session():
    if not hasattr(thread_local, "session"):
        thread_local.session = requests.Session()
    return thread_local.session

def main():
    output_folder = "VanGones"
    os.makedirs(output_folder, exist_ok=True)

    with open("vangogh_artwork_ids.csv", newline="", encoding="utf-8") as csvfile:
        reader = list(csv.DictReader(csvfile))  # convert to list for multiple passes

    def process(row):
        if stop_requested:
            logging.info("Skipping processing due to shutdown request.")
            return
        session = get_session()
        try:
            art_id = row["id"]
            title = sanitize_filename(row["title"])
            logging.info(f"Processing artwork: {art_id} - {title}")
            base_url = get_iiif_base_url(session, art_id)
            if base_url:
                filename = f"{title}_{art_id}.jpg"
                filepath = os.path.join(output_folder, filename)
                if os.path.exists(filepath):
                    logging.warning(f"Already downloaded {filename}, skipping.")
                    return
                download_max_resolution_image(session, base_url, filepath, art_id, title)
            else:
                logging.warning(f"Skipping artwork {art_id} - no base IIIF URL found")
        except Exception as e:
            logging.exception(f"Unexpected error: {e}")
        finally:
            session.close()
    # Wrap the iterable with tqdm for progress tracking
    with ThreadPoolExecutor(max_workers=5) as executor:  # tweak workers for your bandwidth/CPU
        futures = []
        pbar = tqdm(total=len(reader), desc="Downloading artworks")
        try:
            for row in reader:
                if stop_requested:
                    logging.info("Stop requested, no more new tasks submitted.")
                    break
                future = executor.submit(process, row)
                futures.append(future)

            # As futures complete, update progress bar
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"Error in worker thread: {e}")
                pbar.update(1)

        except Exception as e:
            logging.error(f"Error during processing: {e}")
        finally:
            pbar.close()

if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Fatal error while running main()")
    finally:
        save_log_to_file()
