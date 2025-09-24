import asyncio
import hashlib
import logging
from functools import wraps
from multiprocessing import pool

import html2text
import httpx
import httpx_cache

from urllib.parse import urlparse

from toolkit.cache import memory
from toolkit.user_agent import get_user_agent

from langchain.document_loaders import PyMuPDFLoader
from langchain.schema import Document

from bs4 import BeautifulSoup

from options import options

from toolkit.cache import memory

@memory.cache(ignore=["user_agent", "timeout"])
async def fetch_html_with_playwright(url: str, user_agent: str, timeout: int = 30) -> str | None:
    """
    Use Playwright to render the page and return final HTML. Returns None on failure.
    This is a best-effort fallback for sites that block simple HTTP clients or require JS.
    """
    try:
        from playwright.async_api import async_playwright
    except Exception as e:
        logging.error(f"Playwright not available: {e}")
        return None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = await browser.new_context(user_agent=user_agent, locale="en-US")
            page = await context.new_page()

            await page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            })
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            except Exception as e_nav:
                logging.error(f"Playwright navigation failed for {url}: {e_nav}")
                await browser.close()
                return None

            # allow some time for dynamic content
            await page.wait_for_timeout(500)
            content = await page.content()
            await browser.close()
            return content
    except Exception as e:
        logging.error(f"Playwright fetch failed for {url}: {e}")
        return None


@memory.cache(ignore=["client"])
async def process_html_url(url: str, client: httpx.AsyncClient):
    """Asynchronously loads and processes a single HTML URL with HTTPX and Playwright fallback."""
    ua = get_user_agent()
    browser_headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    browser_headers["Referer"] = base

    try:
        # Prefetch base to get cookies / expected headers
        try:
            await client.get(base, headers={"User-Agent": ua, "Referer": base}, timeout=10)
        except Exception:
            pass

        async with client.stream("GET", url, headers=browser_headers) as response:
            # if site blocks us, raise to trigger fallback
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                status = getattr(e.response, "status_code", None)

                logging.error(f"HTTP error for HTML {url}: {status} - response body omitted (streaming)")

                if status == 403 or (status and 400 <= status < 500):
                    if options.get("verbose"):
                        logging.info(f"[DEBUG] HTTP {status} for {url}, trying Playwright fallback.")
                    html = await fetch_html_with_playwright(url, ua, timeout=30)
                    if not html:
                        return None
                else:
                    return None
            else:
                content = await response.aread()
                try:
                    html = content.decode(response.encoding or "utf-8")
                except Exception:
                    html = content.decode("utf-8", errors="replace")

        # parse and wrap as before
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string if soup.title else ""

        h = html2text.HTML2Text()
        h.body_width = 0
        h.ignore_links = True
        h.ignore_images = True
        h.ignore_emphasis = False
        h.ignore_tables = False
        h.mark_code = True

        page_content = h.handle(html)
        doc = Document(page_content=page_content, metadata={"url": url, "title": title, "type": "html"})
        doc.metadata["hash"] = hashlib.sha256(page_content[:1000].encode()).hexdigest()
        return [doc]

    except Exception as e:
        logging.error(f"Failed loading HTML {url}: {e}")


async def process_pdf_url(url: str, client: httpx.AsyncClient):
    """Asynchronously loads and processes a single PDF URL."""
    try:

        response = await client.get(url)
        response.raise_for_status()

        def load_pdf():
            loader = PyMuPDFLoader(url)
            return loader.load()

        pdf_docs = await asyncio.to_thread(load_pdf)

        processed_docs = []
        for doc in pdf_docs:
            doc.metadata.update({
                "url": url,
                "title": "",
                "snippet": "",
                "type": "pdf"
            })
            doc.metadata["hash"] = hashlib.sha256(doc.page_content[:1000].encode()).hexdigest()
            processed_docs.append(doc)
        return processed_docs

    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP error for PDF {url}: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        logging.error(f"Failed loading PDF {url}: {e}")
        return None


async def async_load_documents_from_urls(urls: list[str]):
    """
    Asynchronously loads documents from a list of URLs with retries and caching.
    """
    if options["verbose"]:
        logging.info(f"[DEBUG] Asynchronously scrapping internet for: {urls}")

    transport = httpx.AsyncHTTPTransport(retries=3, http2=True)
    cached_transport = httpx_cache.AsyncCacheControlTransport(
        transport=transport,
        cacheable_methods=('GET',),
        cache=httpx_cache.FileCache(f'{options["cache_dir"]}/.http_cache')
    )

    async with httpx.AsyncClient(transport=cached_transport, http2=True, timeout=30, follow_redirects=True) as client:
        tasks = []
        for url in urls:
            if url.lower().endswith(".pdf"):
                tasks.append(process_pdf_url(url, client))
            else:
                tasks.append(process_html_url(url, client))

        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_docs = []
    for result in results:
        if isinstance(result, list):
            all_docs.extend(result)
        elif result is not None:
            logging.error(f"A task failed with an exception: {result}")


    unique_docs = {doc.metadata["hash"]: doc for doc in all_docs}
    return list(unique_docs.values())

def async_to_sync(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # no running loop -> safe to use asyncio.run
            return asyncio.run(f(*args, **kwargs))
        else:
            # running loop (e.g. Jupyter). apply nest_asyncio if available and run on current loop
            try:
                import nest_asyncio
                nest_asyncio.apply()
            except Exception:
                pass
            # run_until_complete on the current loop (nest_asyncio allows re-entry in notebooks)
            return loop.run_until_complete(f(*args, **kwargs))
    return wrapper

@memory.cache
def load_documents_from_urls(urls: list[str]):
    """
    Loads documents from a list of URLs, handling PDF files separately.
    This is a synchronous wrapper around the async implementation, with caching.

    Args:
        urls: A list of URLs to load.
    Returns:
        A list of loaded and transformed documents.
    """
    return async_to_sync(async_load_documents_from_urls)(urls)
