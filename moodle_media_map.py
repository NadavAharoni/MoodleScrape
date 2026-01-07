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


def login(session, username, password):
    login_url = "https://moodle4.michlala.edu/login/index.php"

    # Step 1: GET login page
    r = session.get(login_url)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    token_input = soup.find("input", {"name": "logintoken"})
    if not token_input:
        raise RuntimeError("Could not find logintoken — login page structure unexpected")

    token = token_input["value"]

    payload = {
        "username": username,
        "password": password,
        "logintoken": token,
    }

    # Step 2: POST credentials
    r = session.post(login_url, data=payload, allow_redirects=True)
    r.raise_for_status()

    # Step 3: verify login success
    if "loginerrors" in r.text.lower():
        raise RuntimeError("Login failed: invalid credentials")

    # Moodle usually redirects to /my/ or the originally requested page
    print("Logged in, final URL:", r.url)


def extract_section_name(section):
    # 1. Best case: data attribute
    name = section.get("data-sectionname")
    if name:
        return name.strip()

    # 2. Visible section name (remove "הקליקו" etc.)
    header = section.select_one(".sectionname")
    if header:
        text = header.get_text(" ", strip=True)
        # remove common UI suffixes
        for suffix in ["הקליקו", "click", "לחצו"]:
            text = text.replace(suffix, "").strip(" -–")
        return text

    # 3. Fallback
    secnum = section.get("data-sectionid", "unknown")
    return f"section_{secnum}"



def extract_sections(course_html, course_url):
    soup = BeautifulSoup(course_html, "html.parser")
    sections = []

    for section in soup.select("li.section"):
        section_name = extract_section_name(section)
        section_slug = slugify(section_name)

        print(f"\nDEBUG — section: {section_slug}")
        for a in section.select("a[href]"):
            print("   ", a["href"])

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

    print(args.username, args.password)

    login(session, args.username, args.password)

    course_html = session.get(args.course_url).text
    sections = extract_sections(course_html, args.course_url)

    for section_name, section_slug, page_links in sections:
        print(f"\nUnit: {section_slug}")

        video_counter = 1

        for page_url in page_links:
            print("DEBUG — fetching page:", page_url)
            r = session.get(page_url)
            print("DEBUG — final URL:", r.url)

            page_html = r.text

            if "zoodle.macam.ac.il" not in page_html:
                print("DEBUG — no zoodle link found in raw HTML")
                continue

            media_ids = extract_media_ids(page_html)
            print("DEBUG — media IDs found:", media_ids)

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
