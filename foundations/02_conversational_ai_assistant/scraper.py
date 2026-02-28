# scraper.py
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
}


def fetch_website_contents(url: str, char_limit: int = 5_000) -> str:
    """
    Fetch and return the title + plain text of the page at `url`.
    Removes script/style/img/input tags, then trims to `char_limit` characters.
    Returns an error string if the request fails.
    """
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        return f"[Error fetching {url}]: {e}"

    soup = BeautifulSoup(response.content, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else "No title found"

    if soup.body:
        for irrelevant in soup.body(["script", "style", "img", "input", "noscript", "svg"]):
            irrelevant.decompose()
        text = soup.body.get_text(separator="\n", strip=True)
    else:
        text = ""

    return (title + "\n\n" + text)[:char_limit]


def fetch_website_links(url: str) -> list[str]:
    """
    Return a deduplicated list of absolute URLs found on the page at `url`.
    Filters out non-HTTP links (mailto:, tel:, javascript:, etc.).
    """
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[Error fetching links from {url}]: {e}")
        return []

    soup = BeautifulSoup(response.content, "html.parser")
    raw_links = [a.get("href") for a in soup.find_all("a") if a.get("href")]

    absolute_links: set[str] = set()
    for link in raw_links:
        full_url = urljoin(url, link)
        if full_url.startswith(("http://", "https://")):
            absolute_links.add(full_url)

    return list(absolute_links)