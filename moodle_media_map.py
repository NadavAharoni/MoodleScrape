import argparse
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import unicodedata


MEDIA_RE = re.compile(
    r"https://zoodle\.macam\.ac\.il/jercol/media/([A-Za-z0-9]+)"
)


def slugify(text):
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace(" ", "_")
    return "".join(c for c in text if c.isalnum() or c in "_-").strip("_")


def login(session, base_url, username, password):
    login_url = urljoin(base_url, "/login/index.php")

    r = session.get(login_url)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    token = soup.find("input", {"name": "logintoken"})["value"]

    payload = {
        "username": username,
        "password": password,
        "logintoken": token,
    }

    r = session.post(login_url, data=payload)
    r.raise_for_status()

    if "loginerrors" in r.text.lower():
        raise RuntimeError("Login failed")


def extract_sections(course_html, course_url):
    soup = BeautifulSoup(course_html, "html.parser")
    sections = []

    for section in soup.select("li.section"):
        header = section.select_one(".sectionname")
        if not header:
            continue

        section_name = header.get_text(strip=True)
        section_slug = slugify(section_name)

        page_links = [
            urljoin(course_url, a["href"])
            for a in section.select("a[href*='mod/page/view.php']")
        ]

        sections.append((section_name, section_slug, page_links))

    return sections


def extract_media_ids(page_html):
    return MEDIA_RE.findall(page_html)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--course-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    session = requests.Session()

    parsed = urlparse(args.course_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    login(session, base_url, args.username, args.password)

    course_html = session.get(args.course_url).text
    sections = extract_sections(course_html, args.course_url)

    for section_name, section_slug, page_links in sections:
        print(f"\nUnit: {section_slug}")

        video_counter = 1

        for page_url in page_links:
            page_html = session.get(page_url).text
            media_ids = extract_media_ids(page_html)

            for media_id in media_ids:
                mp4_url = (
                    f"https://zoodle.macam.ac.il/jercol/files/{media_id}.mp4"
                )

                filename = (
                    f"{section_slug}_{video_counter:02d}.mp4"
                )
                video_counter += 1

                print(f"  - {filename}")
                print(f"    {mp4_url}")


if __name__ == "__main__":
    main()
