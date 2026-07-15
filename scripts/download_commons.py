from __future__ import annotations

import csv
import html
import re
import time
from pathlib import Path
from typing import Any

import requests


# ============================================================
# PROJECT PATHS
# ============================================================

SCRIPT_PATH = Path(__file__).resolve()

# Works when this file is either:
#
# projectPang/download_commons.py
#
# or:
#
# projectPang/scripts/download_commons.py

if SCRIPT_PATH.parent.name.lower() == "scripts":
    PROJECT_ROOT = SCRIPT_PATH.parent.parent
else:
    PROJECT_ROOT = SCRIPT_PATH.parent

IMAGE_DIR = PROJECT_ROOT / "data" / "raw"
METADATA_DIR = PROJECT_ROOT / "metadata"
CSV_PATH = METADATA_DIR / "wikimedia_images.csv"

IMAGE_DIR.mkdir(parents=True, exist_ok=True)
METADATA_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# WIKIMEDIA SETTINGS
# ============================================================

API_URL = "https://commons.wikimedia.org/w/api.php"

# Replace this with your real email or project contact.
HEADERS = {
    "User-Agent": (
        "ProjectPangResearch/1.0 "
        "(Thai Buddha pose classification student research; "
        "contact: jirathanayosyingthumakul@gmail.com)"
    )
}

REQUEST_TIMEOUT = 60
REQUEST_DELAY_SECONDS = 0.5

# Images will be downloaded at approximately this width.
THUMBNAIL_WIDTH = 1400

ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


# ============================================================
# TEXT SEARCHES
# ============================================================

# Search results are only candidate images.
# The candidate_label is not the final ground-truth label.
# Final labels should be assigned manually in Label Studio.

SEARCHES = [
    # --------------------------------------------------------
    # ปางมารวิชัย / Earth-touching Buddha
    # --------------------------------------------------------
    {
        "query": '"earth touching" Buddha',
        "candidate_label": "maravijaya_candidate",
        "limit": 100,
    },
    {
        "query": "Bhumisparsha Buddha",
        "candidate_label": "maravijaya_candidate",
        "limit": 100,
    },
    {
        "query": "Bhūmisparśa mudra",
        "candidate_label": "maravijaya_candidate",
        "limit": 100,
    },
    {
        "query": "ปางมารวิชัย",
        "candidate_label": "maravijaya_candidate",
        "limit": 100,
    },

    # --------------------------------------------------------
    # ปางสมาธิ / Meditation Buddha
    # --------------------------------------------------------
    {
        "query": '"meditation Buddha"',
        "candidate_label": "meditation_candidate",
        "limit": 100,
    },
    {
        "query": "Dhyana Buddha",
        "candidate_label": "meditation_candidate",
        "limit": 100,
    },
    {
        "query": "Dhyāna mudra",
        "candidate_label": "meditation_candidate",
        "limit": 100,
    },
    {
        "query": "ปางสมาธิ",
        "candidate_label": "meditation_candidate",
        "limit": 100,
    },

    # --------------------------------------------------------
    # ปางประทานพร / Varada or blessing pose
    # --------------------------------------------------------
    {
        "query": "Varada mudra",
        "candidate_label": "blessing_candidate",
        "limit": 100,
    },
    {
        "query": "Vārada mudra",
        "candidate_label": "blessing_candidate",
        "limit": 100,
    },
    {
        "query": '"gesture of giving" Buddha',
        "candidate_label": "blessing_candidate",
        "limit": 100,
    },
    {
        "query": '"blessing Buddha" statue',
        "candidate_label": "blessing_candidate",
        "limit": 100,
    },
    {
        "query": "ปางประทานพร",
        "candidate_label": "blessing_candidate",
        "limit": 100,
    },

    # --------------------------------------------------------
    # ปางนาคปรก / Naga-protected Buddha
    # --------------------------------------------------------
    {
        "query": "Mucalinda Buddha",
        "candidate_label": "naga_protected_candidate",
        "limit": 100,
    },
    {
        "query": "Mucilinda Buddha",
        "candidate_label": "naga_protected_candidate",
        "limit": 100,
    },
    {
        "query": '"naga protected Buddha"',
        "candidate_label": "naga_protected_candidate",
        "limit": 100,
    },
    {
        "query": '"naga Buddha"',
        "candidate_label": "naga_protected_candidate",
        "limit": 100,
    },
    {
        "query": "ปางนาคปรก",
        "candidate_label": "naga_protected_candidate",
        "limit": 100,
    },

    # --------------------------------------------------------
    # ปางไสยาสน์ / Reclining Buddha
    # --------------------------------------------------------
    {
        "query": '"reclining Buddha"',
        "candidate_label": "reclining_candidate",
        "limit": 150,
    },
    {
        "query": '"sleeping Buddha"',
        "candidate_label": "reclining_candidate",
        "limit": 100,
    },
    {
        "query": '"reclining Buddha" Thailand',
        "candidate_label": "reclining_candidate",
        "limit": 150,
    },
    {
        "query": "ปางไสยาสน์",
        "candidate_label": "reclining_candidate",
        "limit": 100,
    },
    {
        "query": "พระนอน",
        "candidate_label": "reclining_candidate",
        "limit": 100,
    },

    # --------------------------------------------------------
    # Broad searches
    # These produce mixed poses that must be labeled manually.
    # --------------------------------------------------------
    {
        "query": '"Buddha statue" Thailand',
        "candidate_label": "unknown_candidate",
        "limit": 300,
    },
    {
        "query": '"Buddha image" Thailand',
        "candidate_label": "unknown_candidate",
        "limit": 300,
    },
    {
        "query": '"Thai Buddha" statue',
        "candidate_label": "unknown_candidate",
        "limit": 300,
    },
    {
        "query": "พระพุทธรูป ประเทศไทย",
        "candidate_label": "unknown_candidate",
        "limit": 300,
    },
]


# ============================================================
# COMMONS CATEGORIES
# ============================================================

# Category names must exactly match Wikimedia Commons category names.
# If a category does not exist or contains no direct files, the script
# will simply report zero results and continue.

CATEGORIES = [
    {
        "category": "Category:Vārada mudra",
        "candidate_label": "blessing_candidate",
        "limit": 200,
    },
    {
        "category": "Category:Bhumisparsha mudra",
        "candidate_label": "maravijaya_candidate",
        "limit": 200,
    },
    {
        "category": "Category:Dhyana mudra",
        "candidate_label": "meditation_candidate",
        "limit": 200,
    },
    {
        "category": "Category:Mucalinda",
        "candidate_label": "naga_protected_candidate",
        "limit": 200,
    },
    {
        "category": "Category:Reclining Buddha statues in Thailand",
        "candidate_label": "reclining_candidate",
        "limit": 300,
    },
    {
        "category": "Category:Statues of the Buddha in Thailand",
        "candidate_label": "unknown_candidate",
        "limit": 500,
    },
]


# ============================================================
# CSV SETTINGS
# ============================================================

CSV_FIELDS = [
    "page_id",
    "filename",
    "candidate_label",
    "source_type",
    "source_query",
    "commons_title",
    "commons_page_url",
    "thumbnail_url",
    "original_url",
    "author",
    "license",
    "license_url",
    "credit",
    "description",
    "date_created",
    "categories",
    "width",
    "height",
    "mime_type",
]


# ============================================================
# TEXT AND FILENAME HELPERS
# ============================================================

def clean_html(value: str | None) -> str:
    """Remove HTML tags and normalize whitespace."""

    if not value:
        return ""

    cleaned = html.unescape(value)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned.strip()


def get_metadata_value(
    metadata: dict[str, Any],
    key: str,
) -> str:
    """Extract one value from Wikimedia extmetadata."""

    field = metadata.get(key, {})

    if not isinstance(field, dict):
        return ""

    return clean_html(field.get("value", ""))


def make_safe_filename(
    title: str,
    page_id: int,
    extension: str,
) -> str:
    """Create a Windows-safe filename."""

    title = title.removeprefix("File:")
    stem = Path(title).stem

    stem = re.sub(r'[<>:"/\\|?*]', "_", stem)
    stem = re.sub(r"\s+", "_", stem)
    stem = stem.strip(" ._")

    if not stem:
        stem = "wikimedia_image"

    stem = stem[:120]

    return f"{page_id}_{stem}{extension}"


def load_existing_page_ids() -> set[str]:
    """
    Read Wikimedia page IDs already saved in the metadata CSV.

    This prevents duplicate downloads when multiple searches return
    the same Commons file.
    """

    if not CSV_PATH.exists():
        return set()

    page_ids: set[str] = set()

    try:
        with CSV_PATH.open(
            "r",
            newline="",
            encoding="utf-8-sig",
        ) as csv_file:
            reader = csv.DictReader(csv_file)

            for row in reader:
                page_id = row.get("page_id", "").strip()

                if page_id:
                    page_ids.add(page_id)

    except (OSError, csv.Error) as error:
        print(f"Warning: could not read metadata CSV: {error}")

    return page_ids


# ============================================================
# WIKIMEDIA TEXT SEARCH
# ============================================================

def search_wikimedia(
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Search Wikimedia Commons file pages."""

    results: list[dict[str, Any]] = []
    continuation: dict[str, Any] = {}

    while len(results) < limit:
        batch_size = min(50, limit - len(results))

        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": batch_size,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": THUMBNAIL_WIDTH,
            "iiextmetadatalanguage": "en",
            "format": "json",
            "formatversion": 2,
            **continuation,
        }

        response = requests.get(
            API_URL,
            params=params,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        response_data = response.json()

        if "error" in response_data:
            raise RuntimeError(
                f"Wikimedia API error: {response_data['error']}"
            )

        pages = response_data.get("query", {}).get("pages", [])

        if not isinstance(pages, list) or not pages:
            break

        results.extend(pages)

        if "continue" not in response_data:
            break

        continuation = response_data["continue"]
        time.sleep(REQUEST_DELAY_SECONDS)

    return results[:limit]


# ============================================================
# WIKIMEDIA CATEGORY SEARCH
# ============================================================

def search_wikimedia_category(
    category: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Retrieve files directly contained in a Commons category."""

    results: list[dict[str, Any]] = []
    continuation: dict[str, Any] = {}

    while len(results) < limit:
        batch_size = min(50, limit - len(results))

        params = {
            "action": "query",
            "generator": "categorymembers",
            "gcmtitle": category,
            "gcmnamespace": 6,
            "gcmtype": "file",
            "gcmlimit": batch_size,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": THUMBNAIL_WIDTH,
            "iiextmetadatalanguage": "en",
            "format": "json",
            "formatversion": 2,
            **continuation,
        }

        response = requests.get(
            API_URL,
            params=params,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        response_data = response.json()

        if "error" in response_data:
            print(
                f"Category API error for {category}: "
                f"{response_data['error']}"
            )
            break

        pages = response_data.get("query", {}).get("pages", [])

        if not isinstance(pages, list) or not pages:
            break

        results.extend(pages)

        if "continue" not in response_data:
            break

        continuation = response_data["continue"]
        time.sleep(REQUEST_DELAY_SECONDS)

    return results[:limit]


# ============================================================
# IMAGE DOWNLOADING
# ============================================================

def download_image(
    image_url: str,
    destination: Path,
) -> None:
    """Download one image and verify that it is not empty."""

    temporary_path = destination.with_suffix(
        destination.suffix + ".part"
    )

    temporary_path.unlink(missing_ok=True)

    try:
        with requests.get(
            image_url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            stream=True,
        ) as response:
            response.raise_for_status()

            content_type = response.headers.get(
                "Content-Type",
                "",
            ).lower()

            if not content_type.startswith("image/"):
                raise ValueError(
                    "The URL did not return an image. "
                    f"Content-Type: {content_type}"
                )

            with temporary_path.open("wb") as output_file:
                for chunk in response.iter_content(
                    chunk_size=128 * 1024
                ):
                    if chunk:
                        output_file.write(chunk)

        if not temporary_path.exists():
            raise OSError("The downloaded file was not created.")

        if temporary_path.stat().st_size == 0:
            raise OSError("The downloaded file was empty.")

        temporary_path.replace(destination)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


# ============================================================
# METADATA
# ============================================================

def write_metadata_row(
    writer: csv.DictWriter,
    page: dict[str, Any],
    image_info: dict[str, Any],
    filename: str,
    candidate_label: str,
    source_type: str,
    source_query: str,
) -> None:
    """Write one successfully downloaded file to the CSV."""

    metadata = image_info.get("extmetadata", {})

    if not isinstance(metadata, dict):
        metadata = {}

    writer.writerow(
        {
            "page_id": page.get("pageid", ""),
            "filename": filename,
            "candidate_label": candidate_label,
            "source_type": source_type,
            "source_query": source_query,
            "commons_title": page.get("title", ""),
            "commons_page_url": image_info.get(
                "descriptionurl",
                "",
            ),
            "thumbnail_url": image_info.get("thumburl", ""),
            "original_url": image_info.get("url", ""),
            "author": get_metadata_value(metadata, "Artist"),
            "license": get_metadata_value(
                metadata,
                "LicenseShortName",
            ),
            "license_url": get_metadata_value(
                metadata,
                "LicenseUrl",
            ),
            "credit": get_metadata_value(metadata, "Credit"),
            "description": get_metadata_value(
                metadata,
                "ImageDescription",
            ),
            "date_created": get_metadata_value(
                metadata,
                "DateTimeOriginal",
            ),
            "categories": get_metadata_value(
                metadata,
                "Categories",
            ),
            "width": image_info.get("width", ""),
            "height": image_info.get("height", ""),
            "mime_type": image_info.get("mime", ""),
        }
    )


# ============================================================
# RESULT PROCESSING
# ============================================================

def process_pages(
    pages: list[dict[str, Any]],
    source_type: str,
    source_query: str,
    candidate_label: str,
    writer: csv.DictWriter,
    existing_page_ids: set[str],
) -> tuple[int, int, int]:
    """
    Download a list of Wikimedia file pages.

    Returns:
        downloaded_count
        skipped_count
        failed_count
    """

    downloaded_count = 0
    skipped_count = 0
    failed_count = 0

    print(f"API results found: {len(pages)}")

    for index, page in enumerate(pages, start=1):
        title = page.get("title", "Untitled file")
        page_id = str(page.get("pageid", ""))

        print(f"\n[{index}/{len(pages)}] {title}")

        if not page_id:
            print("  Skipped: missing Wikimedia page ID.")
            skipped_count += 1
            continue

        if page_id in existing_page_ids:
            print("  Skipped: already downloaded.")
            skipped_count += 1
            continue

        image_info_list = page.get("imageinfo", [])

        if not image_info_list:
            print("  Skipped: no image information.")
            skipped_count += 1
            continue

        image_info = image_info_list[0]

        if not isinstance(image_info, dict):
            print("  Skipped: invalid image information.")
            skipped_count += 1
            continue

        mime_type = image_info.get("mime", "")

        if mime_type not in ALLOWED_MIME_TYPES:
            print(
                f"  Skipped: unsupported MIME type "
                f"{mime_type!r}."
            )
            skipped_count += 1
            continue

        image_url = (
            image_info.get("thumburl")
            or image_info.get("url")
        )

        if not image_url:
            print("  Skipped: no downloadable image URL.")
            skipped_count += 1
            continue

        extension = ALLOWED_MIME_TYPES[mime_type]

        filename = make_safe_filename(
            title=title,
            page_id=int(page_id),
            extension=extension,
        )

        output_path = IMAGE_DIR / filename

        # If the image exists but its CSV row is missing, skip it
        # instead of overwriting it.
        if output_path.exists():
            print("  Skipped: file already exists locally.")
            existing_page_ids.add(page_id)
            skipped_count += 1
            continue

        try:
            print(f"  Candidate label: {candidate_label}")
            print(f"  Saving to: {output_path}")

            download_image(
                image_url=image_url,
                destination=output_path,
            )

            write_metadata_row(
                writer=writer,
                page=page,
                image_info=image_info,
                filename=filename,
                candidate_label=candidate_label,
                source_type=source_type,
                source_query=source_query,
            )

            existing_page_ids.add(page_id)
            downloaded_count += 1

            print(
                f"  Saved successfully "
                f"({output_path.stat().st_size:,} bytes)."
            )

        except (
            requests.RequestException,
            OSError,
            ValueError,
            RuntimeError,
        ) as error:
            output_path.unlink(missing_ok=True)
            print(f"  Download failed: {error}")
            failed_count += 1

        time.sleep(REQUEST_DELAY_SECONDS)

    return downloaded_count, skipped_count, failed_count


def process_text_search(
    query: str,
    candidate_label: str,
    limit: int,
    writer: csv.DictWriter,
    existing_page_ids: set[str],
) -> tuple[int, int, int]:
    """Search by text and download the results."""

    print("\n" + "=" * 70)
    print(f'Searching Wikimedia for: "{query}"')
    print(f"Candidate label: {candidate_label}")
    print("=" * 70)

    try:
        pages = search_wikimedia(
            query=query,
            limit=limit,
        )

    except (
        requests.RequestException,
        RuntimeError,
    ) as error:
        print(f"Search failed: {error}")
        return 0, 0, 1

    return process_pages(
        pages=pages,
        source_type="text_search",
        source_query=query,
        candidate_label=candidate_label,
        writer=writer,
        existing_page_ids=existing_page_ids,
    )


def process_category(
    category: str,
    candidate_label: str,
    limit: int,
    writer: csv.DictWriter,
    existing_page_ids: set[str],
) -> tuple[int, int, int]:
    """Download files directly contained in a category."""

    print("\n" + "=" * 70)
    print(f'Reading Wikimedia category: "{category}"')
    print(f"Candidate label: {candidate_label}")
    print("=" * 70)

    try:
        pages = search_wikimedia_category(
            category=category,
            limit=limit,
        )

    except requests.RequestException as error:
        print(f"Category request failed: {error}")
        return 0, 0, 1

    return process_pages(
        pages=pages,
        source_type="category",
        source_query=category,
        candidate_label=candidate_label,
        writer=writer,
        existing_page_ids=existing_page_ids,
    )


# ============================================================
# MAIN PROGRAM
# ============================================================

def main() -> None:
    print("=" * 70)
    print("PROJECT PANG — WIKIMEDIA COMMONS DOWNLOADER")
    print("=" * 70)
    print(f"Script file:     {SCRIPT_PATH}")
    print(f"Project root:    {PROJECT_ROOT}")
    print(f"Image directory: {IMAGE_DIR}")
    print(f"Metadata CSV:    {CSV_PATH}")
    print("=" * 70)

    existing_page_ids = load_existing_page_ids()

    print(
        f"Previously recorded Wikimedia files: "
        f"{len(existing_page_ids)}"
    )

    csv_has_content = (
        CSV_PATH.exists()
        and CSV_PATH.stat().st_size > 0
    )

    total_downloaded = 0
    total_skipped = 0
    total_failed = 0

    with CSV_PATH.open(
        "a",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=CSV_FIELDS,
        )

        if not csv_has_content:
            writer.writeheader()
            csv_file.flush()

        # First use targeted text searches.
        for search in SEARCHES:
            downloaded, skipped, failed = process_text_search(
                query=search["query"],
                candidate_label=search["candidate_label"],
                limit=search["limit"],
                writer=writer,
                existing_page_ids=existing_page_ids,
            )

            total_downloaded += downloaded
            total_skipped += skipped
            total_failed += failed

            csv_file.flush()

        # Then retrieve files from Commons categories.
        for category_config in CATEGORIES:
            downloaded, skipped, failed = process_category(
                category=category_config["category"],
                candidate_label=category_config[
                    "candidate_label"
                ],
                limit=category_config["limit"],
                writer=writer,
                existing_page_ids=existing_page_ids,
            )

            total_downloaded += downloaded
            total_skipped += skipped
            total_failed += failed

            csv_file.flush()

    print("\n" + "=" * 70)
    print("DOWNLOAD COMPLETE")
    print("=" * 70)
    print(f"Downloaded: {total_downloaded}")
    print(f"Skipped:    {total_skipped}")
    print(f"Failed:     {total_failed}")
    print(f"Images:     {IMAGE_DIR}")
    print(f"Metadata:   {CSV_PATH}")
    print("=" * 70)


if __name__ == "__main__":
    main()