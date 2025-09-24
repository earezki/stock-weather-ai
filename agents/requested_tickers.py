import pandas as pd
import requests
import time
import random
from io import StringIO
import logging

from options import options

from toolkit.proxy_pool import get_proxy
from toolkit.user_agent import get_user_agent
from toolkit.cache import memory, timestamp_key

from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

@memory.cache
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def scrape_market_data(timestamp_key):
    """
    Scrapes Yahoo Finance for the raw data of top stock market gainers and losers.

    Args:
        timestamp_key: An integer used as a cache key to avoid redundant requests.

    Returns:
        A tuple containing two pandas DataFrames: (gainers, losers).
        Returns (None, None) if data cannot be retrieved.
    """
    headers = {
        'User-Agent': get_user_agent()
    }
    proxy = get_proxy()

    session = requests.Session()
    session.headers.update(headers)

    if proxy and options['use_proxies'] is True:
        session.proxies = {"http": proxy, "https": proxy}
        logger.info(f"Using proxy: {proxy}")

    if options.get('timeout'):
        session.timeout = options['timeout']

    logger.info("Scraping Yahoo Finance for market movers...")

    gainers_url = "https://finance.yahoo.com/gainers"
    response_gainers = session.get(gainers_url)
    response_gainers.raise_for_status()
    gainers_df = pd.read_html(StringIO(response_gainers.text))[0]

    logger.info("Successfully scraped raw gainer data.")

    # add a delay to avoid being blocked
    time.sleep(random.uniform(1, 3))

    losers_url = "https://finance.yahoo.com/losers"
    response_losers = session.get(losers_url)
    response_losers.raise_for_status()
    losers_df = pd.read_html(StringIO(response_losers.text))[0]
    logger.info("Successfully scraped raw loser data.")

    return gainers_df, losers_df

def get_top_movers():
    """
    Fetches and formats market movers into a dictionary object with ticker and name.
    Returns cached result if available.
    """

    logger.info("Fetching new market movers data.")

    try:
        # used as a cache key to avoid redundant requests
        current_timestamp_key = timestamp_key(options['movers']['cache_duration'])
        gainers_df, losers_df = scrape_market_data(current_timestamp_key)
    except Exception as e:
        logger.error(f"Failed to scrape market data: {e}")
        gainers_df, losers_df = None, None

    if gainers_df is None or losers_df is None:
        return None

    if 'Symbol' in gainers_df.columns and 'Name' in gainers_df.columns:
        gainers_df.dropna(subset=['Symbol', 'Name'], inplace=True)
        gainers_subset = gainers_df[['Symbol', 'Name']].rename(
            columns={'Symbol': 'ticker', 'Name': 'name'}
        )
        gainers_list = gainers_subset.to_dict('records')
    else:
        logger.error("Could not find 'Symbol' or 'Name' columns in gainers data.")
        gainers_list = []

    if 'Symbol' in losers_df.columns and 'Name' in losers_df.columns:
        losers_df.dropna(subset=['Symbol', 'Name'], inplace=True)
        losers_subset = losers_df[['Symbol', 'Name']].rename(
            columns={'Symbol': 'ticker', 'Name': 'name'}
        )
        losers_list = losers_subset.to_dict('records')
    else:
        logger.error("Could not find 'Symbol' or 'Name' columns in losers data.")
        losers_list = []

    market_movers = {
        "gainers": gainers_list, 
        "losers": losers_list
    }

    return market_movers