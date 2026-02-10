
# %%
from bs4 import BeautifulSoup
import requests

 
# Standard headers to fetch a website
# "I am actually Chrome 117, but I act just like Safari and have the rendering capabilities of Gecko (Firefox), all while running on Windows 10. So, just hand over your best web content already!"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
}


def fetch_website_contents(url):
    """
    Return the title and contents of the website at the given url;
    truncate to 2,000 characters as a sensible limit

    # Goal: Extract plain text and filter out noise.
    # 1. response.content: Get raw binary data.
    # 2. soup.title.string: Get browser tab title.
    # 3. decompose(): Remove script/style/img/input to keep only text.
    # 4. get_text: Strip tags and join text with newlines.
    # 5. [:2_000]: Limit to 2,000 chars for safety.
    """
    response = requests.get(url, headers=headers)                           
    soup = BeautifulSoup(response.content, "html.parser")
    title = soup.title.string if soup.title else "No title found"
    if soup.body:
        for irrelevant in soup.body(["script", "style", "img", "input"]):
            irrelevant.decompose()
        text = soup.body.get_text(separator="\n", strip=True)
    else:
        text = ""
    return (title + "\n\n" + text)[:2_000]


# def fetch_website_links(url):
#     """
#     Return the links on the webiste at the given url
#     I realize this is inefficient as we're parsing twice! This is to keep the code in the lab simple.
#     Feel free to use a class and optimize it!
#     """
#     response = requests.get(url, headers=headers)
#     soup = BeautifulSoup(response.content, "html.parser")
#     links = [link.get("href") for link in soup.find_all("a")]
#     return [link for link in links if link]


from urllib.parse import urljoin

def fetch_website_links(url):
    """
    Return a list of unique, absolute URLs found on the website at the given url.

    # Goal: Extract all valid hyperlinks and convert them to usable absolute paths.
    # 1. requests.get: Fetch the page content using predefined headers.
    # 2. BeautifulSoup: Parse the HTML structure to find anchor tags.
    # 3. urljoin: Merge the base URL with relative paths (e.g., '/contact' -> 'https://site.com/contact').
    # 4. set(): Remove duplicate links to ensure the list is clean and efficient.
    # 5. startswith('http'): Filter out non-web links like 'mailto:', 'tel:', or javascript fragments.
    """
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    
    # Get the href attributes of all <a> tags.
    raw_links = [link.get("href") for link in soup.find_all("a") if link.get("href")]
    
    # Remove duplicates and onvert to absolute paths.
    absolute_links = set()
    for link in raw_links:
        full_url = urljoin(url, link)
        if full_url.startswith(("http://", "https://")): 
            absolute_links.add(full_url)
            
    return list(absolute_links)