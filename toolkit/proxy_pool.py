import requests
from bs4 import BeautifulSoup
import ipaddress
from itertools import cycle
import logging

logger = logging.getLogger(__name__)

def _is_valid_ip(ip):
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def _is_valid_port(port):
    try:
        port_num = int(port)
        return 0 < port_num < 65536
    except ValueError:
        return False

def _is_valid_proxy(proxy):
    try:
        response = requests.get("http://ipinfo.io", proxies={"http": proxy}, timeout=5)
        return response.status_code == 200
    except:
        return False

def _get_proxies():
    provider_list = [
        #'https://www.us-proxy.org/',
        #'https://free-proxy-list.net/',
        'https://www.sslproxies.org/',
        #'https://www.proxy-list.download/HTTP',
        #'https://free-proxy-list.net/en/google-proxy.html',
        #'https://free-proxy-list.net/en/uk-proxy.html'
    ]

    proxy_list = []

    for provider in provider_list:
        try:
            logger.info(f"Getting proxies from: {provider}")
            page = requests.get(provider)
            soup = BeautifulSoup(page.text, 'html.parser')
                
            for row in soup.find_all('tr'):
                cols = row.find_all('td')
                if len(cols) >= 2:  # Ensure there are at least two columns (IP and Port)
                    ip_address = cols[0].get_text(strip=True)
                    port = cols[1].get_text(strip=True)

                    if _is_valid_ip(ip_address) and _is_valid_port(port):
                        proxy_list.append(f"{ip_address}:{port}")
            
        except:
            logger.error("Error with provider: " + provider)
            continue

    return set(proxy_list[:10]) # limit to first 10 proxies

def _get_proxy_pool():
    proxy_list = _get_proxies()

    logger.info(f"Retrieved {len(proxy_list)} proxies.")
    
    # proxy_list = [proxy for proxy in proxy_list if _is_valid_proxy(proxy)]
    # print(f"[INFO] {len(proxy_list)} proxies are valid and working.")

    proxy_pool = cycle(proxy_list) if proxy_list else cycle([None])
    return proxy_pool

proxy_pool = _get_proxy_pool()

def get_proxy():
    return next(proxy_pool)