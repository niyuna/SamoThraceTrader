import requests
import json
# import logging
from datetime import datetime
from loguru import logger

# logger = logging.getLogger(__name__)

def get_stockmaster(url = 'http://127.0.0.1:8001/metadata/stockmaster', date = None):
    try:
        if date is None:
            current_date = datetime.now()
            date = current_date.strftime("%Y%m%d")
        url = url + f"_{date}"
        logger.info(f"getting stockmaster from {url}")
        response = requests.get(url)
        j = response.json()
        j = json.loads(j)
        for sc, v in j.items():
            v['market_cap'] = v.get('calcSharesOutstanding', 0) * v['basePrice10'] / 10
    except Exception as e:
        logger.error(f"error getting stockmaster: {e}")
        return {}
    logger.info(f"stockmaster length: {len(j)}")
    return j


def should_do_agg(sc, stock_master, filter_list):
    if any(sc in v for k, v in filter_list.items()):
        return True
    if stock_master[sc].get('market_cap', 0) < 100_000_000_000:
        return False

    init_price_diff = stock_master[sc].get('init_price_diff', None)
    if init_price_diff is None:
        return True
    if init_price_diff > gu_condition:
        filter_list['gu'].add(sc)
        return True
    if init_price_diff < gd_condition:
        filter_list['gd'].add(sc)
        return True
    return False