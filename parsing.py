import numpy as np
import pandas as pd
import time
import re
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

GOLD_APPLE_FACE_COSMETICS = 'https://goldapple.ru/uhod/uhod-za-licom/'
SUBDIRECTORIES = {
    'ochischenie-i-demakijazh': 5828,
    'tonizirovanie': 2642,
    'osnovnoj-uhod': 8121,
    'special-nyj-uhod': 8722,
    'antivozrastnoj-uhod-za-licom': 6971,
    'kremy': 5321,
    'syvorotki': 3991,
    'maski': 3730,
    'patchi': 668,
    'pedy': 167,
    'skraby-i-pilingi': 737
}
GOLD_APPLE_REVIEW = 'https://goldapple.ru/review/product/'

CATALOG_TIMEOUT = 5
REQUEST_TIMEOUT = 15
MAX_CACHE_VALUE = 2400
MAX_VALUE = 25000

content_pattern = r"content=\"([^\"]*)\""
rating_pattern = r"<div class=\"([^\"]*)\" itemprop=\"ratingValue\">([^\"]*)</div>"
is_for_skin_pattern = r"<dt class=\"([^\"]*)\"><span>область применения</span></dt> <dt class=\"([^\"]*)\"><span>([^\"]*)</span></dt>"
composition_pattern = r"<div text=\"состав\" value=\"([^\"]*)\"><!-- --> <!-- --> <div class=\"([^\"]*)\">([^\"]*)</div> <!-- --></div></div>"


def get_new_products_urls(links: list) -> set:
    urls = set()
    pattern = r"https://goldapple.ru/(\d+)([^\"]*)"
    for link in links:
        url = link.get_attribute("href")
        if re.search(pattern, url) is not None:
            urls.add(url)
    return urls


def get_button_xpath(ind: int):
    return '/html/body/div/div/div/main/div[2]/div[' + str(ind) + ']/button[1]'

def extract_products(driver, current_subdir):
    try:
        driver.get(GOLD_APPLE_FACE_COSMETICS + current_subdir)
        time.sleep(CATALOG_TIMEOUT)

        set_product_urls = set()

        links = driver.find_elements(By.TAG_NAME, "a")
        set_product_urls.update(get_new_products_urls(links))

        ind = 2
        limit_product_cnt = min(SUBDIRECTORIES[current_subdir], MAX_CACHE_VALUE)
        while limit_product_cnt > len(set_product_urls):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(CATALOG_TIMEOUT)

            links = driver.find_elements(By.TAG_NAME, "a")
            set_product_urls.update(get_new_products_urls(links))

            driver.execute_script("arguments[0].click();", WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, get_button_xpath(ind)))))
            ind = ind + 1

        return set_product_urls
    except Exception as unknown:
        return set_product_urls


def load_page(url):
    req = requests.get(url, timeout=REQUEST_TIMEOUT)
    soup = BeautifulSoup(req.text, "html.parser")
    return soup


def parse_product_id(soup):
    return int(re.search(content_pattern, str(soup.find('meta', itemprop='sku'))).group(1))


def parse_price(soup):
    return int(re.search(content_pattern, str(soup.find('meta', itemprop='price'))).group(1))


def parse_cnt_reviews(soup):
    return int(re.search(content_pattern, str(soup.find('meta', itemprop='reviewCount'))).group(1))


def parse_rating(soap):
    return float(re.search(rating_pattern, str(soap.find('div', itemprop='ratingValue'))).group(2)
                 .replace(' ', '').replace('\n', ''))


def parse_description(description):
    return [
        re.search(is_for_skin_pattern, description).group(3),
        re.search(composition_pattern, description).group(3)
    ]


def parse_product(url) -> list:
    try:
        soup = load_page(url)

        article = parse_product_id(soup)
        price = parse_price(soup)

        request_review = requests.get(GOLD_APPLE_REVIEW + str(article), timeout=REQUEST_TIMEOUT)
        cnt_reviews = 0
        rating = 0
        if request_review.status_code == 200:
            soap_review = BeautifulSoup(request_review.text, "html.parser")
            cnt_reviews = parse_cnt_reviews(soap_review)
            rating = parse_rating(soap_review)

        description = str(soup.findAll('div', value='Description_0')[0])
        is_for_skin, composition = parse_description(description)

        if is_for_skin != 'лицо':
            return list()

        return [article, price, rating, cnt_reviews, composition]
    except Exception as e:
        print(e)
        return list()


def process_and_store_products(product_urls: list):
    iterate = 0
    cnt = 0
    g_article = np.empty(MAX_VALUE, dtype=int)
    g_price = np.empty(MAX_VALUE, dtype=int)
    g_rating = np.empty(MAX_VALUE, dtype=float)
    g_cnt_reviews = np.empty(MAX_VALUE, dtype=int)
    g_composition = np.empty(MAX_VALUE, dtype='U1500')

    for url in product_urls:
        result = parse_product(url)
        if len(result) > 0:
            g_article[cnt] = result[0]
            g_price[cnt] = result[1]
            g_rating[cnt] = result[2]
            g_cnt_reviews[cnt] = result[3]
            g_composition[cnt] = result[5]
            cnt += 1
        iterate += 1
        if iterate % 100 == 0:
            print(iterate)
    print()
    print('cnt = ', cnt)

    data = pd.DataFrame(
        list(zip(g_article[:cnt], g_price[:cnt], g_rating[:cnt], g_cnt_reviews[:cnt], g_composition[:cnt])),
        columns=['product_id', 'price', 'rating', 'review_count', 'composition']
    )

    data.to_csv("gold_apple_data.csv", index=False)


def parse_gold_apple():
    product_urls = set()
    for subdir in SUBDIRECTORIES.keys():
        try:
            chrome_options = Options()
            chrome_options.add_argument('--no-sandbox')
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            product_urls.update(extract_products(driver, subdir))
            driver.quit()
            print('subdir = ', subdir, ' len_product_urls = ', len(product_urls))
        except Exception as e:
            print(e)
    print()
    process_and_store_products(list(product_urls))


#if __name__ == "__main__":
    #parse_gold_apple()
