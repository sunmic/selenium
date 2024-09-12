DATA_DIR = f'E:\work\selenium'
ADS_DIR = f'{DATA_DIR}/ads'
ADS_UPDATE_DIR = f'{DATA_DIR}/ads_update'
EXPIRED_DIR = f'{DATA_DIR}/ads_expired'
NEXT_DATA_DIR = f'{DATA_DIR}/next_data'
OTHER_DIR = f'{DATA_DIR}/other_data'
UPS_DIR = f'{DATA_DIR}/ups'
PROMO_DIR = f'{DATA_DIR}/promo'
SCAN_DIR = f'{DATA_DIR}/scan'

import os
from datetime import datetime, timedelta, date
import json
import time
import zoneinfo
from jsondiff import diff
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
import base64
import re

if not os.path.exists(ADS_DIR):
    os.makedirs(ADS_DIR)
if not os.path.exists(ADS_UPDATE_DIR):
    os.makedirs(ADS_UPDATE_DIR)
if not os.path.exists(EXPIRED_DIR):
    os.makedirs(EXPIRED_DIR)
if not os.path.exists(NEXT_DATA_DIR):
    os.makedirs(NEXT_DATA_DIR)
if not os.path.exists(OTHER_DIR):
    os.makedirs(OTHER_DIR)
if not os.path.exists(UPS_DIR):
    os.makedirs(UPS_DIR)
if not os.path.exists(PROMO_DIR):
    os.makedirs(PROMO_DIR)
if not os.path.exists(SCAN_DIR):
    os.makedirs(SCAN_DIR)

def read_ads_ups(public_id=''):
    ups = {}

    files = [file for file in os.listdir(UPS_DIR) if public_id in file]
    public_id_fun = lambda x : x.split('-')[1]
    
    for filename in files:
        public_id = public_id_fun(filename)
        access_time = datetime.fromisoformat('-'.join(filename[:-5].split('-')[2:]).replace('_', ':'))
        with open(f'{UPS_DIR}/{filename}', 'r') as file:
            data = json.loads(file.read())
            entry = dict(
                            access_time=access_time,
                            up=data
                        )
        if public_id not in ups.keys():
            ups[public_id] = []
        ups[public_id].append(entry)
    
    for public_id in ups.keys():
        ups[public_id] = sorted(ups[public_id], key = lambda x : x['access_time'])
    
    return ups

def read_ads_promo(public_id=''):
    promo = {}

    files = [file for file in os.listdir(PROMO_DIR) if public_id in file]
    public_id_fun = lambda x : x.split('-')[1]
    
    for filename in files:
        public_id = public_id_fun(filename)
        access_time = datetime.fromisoformat('-'.join(filename[:-5].split('-')[2:]).replace('_', ':'))
        with open(f'{PROMO_DIR}/{filename}', 'r') as file:
            data = json.loads(file.read())
            entry = dict(
                            access_time=access_time,
                            promo=data
                        )
        if public_id not in promo.keys():
            promo[public_id] = []
        promo[public_id].append(entry)
    
    for public_id in promo.keys():
        promo[public_id] = sorted(promo[public_id], key = lambda x : x['access_time'])
    
    return promo

def read_ads_extra(public_id=''):
    extra = {}

    files = [file for file in os.listdir(OTHER_DIR) if public_id in file]
    public_id_fun = lambda x : x.split('-')[1]
    
    for filename in files:
        public_id = public_id_fun(filename)
        access_time = datetime.fromtimestamp(int(filename[:-5].split('-')[2]))
        with open(f'{OTHER_DIR}/{filename}', 'r') as file:
            data = json.loads(file.read())
            entry = dict(
                            access_time=access_time,
                            extra=data
                        )
        if public_id not in extra.keys():
            extra[public_id] = []
        extra[public_id].append(entry)
    
    for public_id in extra.keys():
        extra[public_id] = sorted(extra[public_id], key = lambda x : x['access_time'])
    
    return extra


def read_ads_from_dir(public_id=''):
    print("Loading ads from directory.")
    ads = {}
    ad_files = [file for file in os.listdir(ADS_DIR) if public_id in file]
    upd_files = [file for file in os.listdir(ADS_UPDATE_DIR) if public_id in file]
    expired_files = [file for file in os.listdir(EXPIRED_DIR) if public_id in file]
    
    ad_files_and_dirs = list(zip(ad_files, [ADS_DIR] * len(ad_files))) \
                    + list(zip(upd_files, [ADS_UPDATE_DIR] * len(upd_files))) \
                    + list(zip(expired_files, [EXPIRED_DIR] * len(expired_files)))

    assert len(ad_files_and_dirs) == len(ad_files) + len(upd_files) + len(expired_files)

    prefix_fun = lambda x : '-'.join(x.split('-')[:2])
    other_dir_prefixes = [prefix_fun(x) for x in os.listdir(OTHER_DIR)]

    for (filename, directory) in ad_files_and_dirs:
        public_id = filename[:-5].split('-')[1]
        access_time = datetime.fromtimestamp(int(filename[:-5].split('-')[2]))
        prefix_fun = lambda x : '-'.join(x.split('-')[:2])
        with open(f"{directory}/{filename}", 'r') as file:
            content = file.read()
            data = json.loads(content)
            entry = {'access_time' : access_time,
                        'ad' : data,
                        'hasCenoskop' : prefix_fun(filename) in other_dir_prefixes,
                        'expired' : directory == EXPIRED_DIR
                        }
        if public_id not in ads.keys():
            ads[public_id] = []
        ads[public_id].append(entry)

    for public_id in ads.keys():
        ads[public_id] = sorted(ads[public_id], key = lambda x : x['access_time'])
    
    count = len(ads.keys())
    print(f"Loading of {count} ads finished.")
    return ads

def scrape_single(driver, ads, price_updated=False, article_updated=False):
    title = driver.title
    if '404' in title:
        time.sleep(5)
        driver.refresh()
    # scroll down the webpage to get all results
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1)
    min_price = driver.find_elements(by=By.XPATH, value='//*[@data-cy="ad.avm-module.min-price"]')
    max_price = driver.find_elements(by=By.XPATH, value='//*[@data-cy="ad.avm-module.max-price"]')
    min_price_value = [e.text for e in min_price]
    max_price_value = [e.text for e in max_price]
    
    expired = driver.find_elements(by=By.XPATH, value='//div[@data-cy="expired-ad-alert"]')
    is_expired = len(expired) > 0

    inactive = driver.find_elements(by=By.XPATH, value='//div[@data-cy="redirectedFromInactiveAd"]')
    is_inactive = len(inactive) > 0
    if is_inactive:
        print("Redirected from inactive ad")
        return  # TBD

    next_data = driver.find_elements(by=By.XPATH, value='//script[@id="__NEXT_DATA__"]')[0]
    all_data = next_data.get_attribute('innerHTML')
    jsontext = json.loads(all_data)
    ad = jsontext.get('props').get('pageProps').get('ad')
    public_id = ad.get('publicId')
    ad_id = str(ad.get('id')) + '-' + public_id + '-' + str(int(time.time()))

    if public_id in ads.keys():
        None # print(f"Already has basic data for {public_id}")
        prev_date = ads[public_id][-1]['ad']['modifiedAt']
        this_date = ad['modifiedAt']
        modified = this_date != prev_date
        if article_updated != modified:
            None # breakpoint position
        if price_updated or article_updated or modified:
            with open(f'{ADS_UPDATE_DIR}/{ad_id}.json', 'w') as file:
                file.write(json.dumps(ad))
                ads[public_id].append({'access_time' : datetime.now(),
                            'ad' : ad,
                            'hasCenoskop' : ads[public_id][-1]['hasCenoskop']  # keep value
                            })  # sort not needed as time flows forward
    else:
        with open(f'{NEXT_DATA_DIR}/{ad_id}.json', 'w') as file:
            file.write(json.dumps(jsontext))
        with open(f'{ADS_DIR}/{ad_id}.json', 'w') as file:
            file.write(json.dumps(ad))
        ads[public_id] = [{'access_time' : datetime.now(),
                        'ad' : ad,
                        'hasCenoskop' : False
                        }]
    
    if is_expired:
        with open(f'{EXPIRED_DIR}/{ad_id}.json', 'w') as file:
            file.write(json.dumps(ad))
            ads[public_id].append({'access_time' : datetime.now(),
                        'ad' : ad,
                        'hasCenoskop' : ads[public_id][-1]['hasCenoskop']  # keep value
                        })  # sort not needed as time flows forward

    # if len(min_price_value) > 0 and (not ads[public_id][-1]['hasCenoskop'] or price_updated or article_updated):
    if len(min_price_value) > 0:
        with open(f'{OTHER_DIR}/{ad_id}.json', 'w') as file:
            other = {
                        "id"        : ad.get('id'),
                        "publicId"  : ad.get('publicId'),
                        "min_price" : min_price_value[0].replace(" zł", "").replace(" ", ""),
                        "max_price" : max_price_value[0].replace(" zł", "").replace(" ", "")
                    }
            file.write(json.dumps(other))
        # ads[public_id][-1]['hasCenoskop'] = True
        for entry in ads[public_id]:
            entry['hasCenoskop'] = True    
        # print("Gathered cenoskop min/max prices.")
    elif not is_expired:
        print("Missing cenoskop min/max prices!")

def process_promoted(driver):
        promoted_l = driver.find_elements(by=By.XPATH, value='//div[@data-cy="search.listing.promoted"]')
        while (len(promoted_l) == 0):
            time.sleep(2)
            print("--> Próba przywrócenia strony z wynikami (refresh/back)")
            if 'wyniki' in driver.current_url:
                driver.refresh()
            else:
                driver.back()
            promoted_l = driver.find_elements(by=By.XPATH, value='//div[@data-cy="search.listing.promoted"]')
        promoted = promoted_l[0]
        promoted_article_list = promoted.find_elements(by=By.XPATH, value='.//article[@data-cy="listing-item"]')
        # print('Promoted:', len(promoted_article_list))
        assert len(promoted_article_list) == 3
        for article in promoted_article_list:
            links = article.find_elements(by=By.XPATH, value='.//a[@data-cy="listing-item-link"]')
            assert len(links) == 1
            url = links[0].get_attribute('href')
            public_id = url.split("-")[-1][2:]
            entry = {
                'public_id' : public_id,
                'promo_date': date.today().isoformat()
            }
            # g_promoted.append(entry)

            promo_filename = f"{PROMO_DIR}/promo-{public_id}-{entry['promo_date']}.json"
            if not os.path.exists(promo_filename):
                with open(promo_filename, 'w') as file:
                    file.write(json.dumps(entry))
        return promoted_article_list

def check_inactive(driver, ads, scan):
    assert scan['state'] == 'COMPLETED'
    
    if 'city' in scan.keys():
        city = scan['city']
    else:
        for candidate in ['poznan', 'wroclaw']:
            if candidate in scan['website']:
                city = candidate
    
    city_ids = [k for (k,v) in ads.items() if v[-1]['ad']['target']['City'] == city]

    public_id_fun = lambda x : x.split('-')[1]
    expired_ids = [public_id_fun(x) for x in os.listdir(EXPIRED_DIR)]

    inactive_ids = list(set(city_ids) - set(scan['seen_ids']) - set(expired_ids))
    total = len(inactive_ids)
    print('Nieaktywnych ogłoszeń do sprawdzenia:', total)

    inactive_urls = [ads[id][-1]['ad']['url'] for id in inactive_ids]
    for num, url in enumerate(inactive_urls):
        process_promoted(driver)
        print(f"[{num+1}/{total}]Following inactive", url)
        driver.get(url)
        time.sleep(1)
        scrape_single(driver=driver, ads=ads)
        driver.back()
        time.sleep(1)
    process_promoted(driver)

def ad_to_article_entry(ad):
    return {
        'public_id' : ad['publicId'],
        'url' : ad['url'],
        # 'address' : address,
        'title' : ad['title'].replace('   ', ' ').replace('  ', ' ').replace('\xa0', ' '), #.replace(' /', '/'),
        'photo' : base64.b64decode(ad['target']['Photo']).decode('utf-8'),
        'price' : ad['target']['Price'],  
        'price_per_square_m' : ad['target']['Price_per_m'],
        'rooms' : ad['target']['Rooms_num'][0] if ad['target']['Rooms_num'][0] != 'more' else '10+',
        # 10+ dedykowane dla https://www.otodom.pl/pl/oferta/poddasze-w-pieknie-rewitalizowanej-kamienicy-ID4qr6K
        'area' : ad['target']['Area'],  
        # # 'floor' : det_as_dict['Piętro'],  # TBD ta informacja może nie być dostępna
        # # 'podbite' : up_text,
        # 'up_datetime' : up_datetime.isoformat() if up_ind else ""  # datetime.fromtimestamp(0).isoformat()
    }

# define main function
def scrape(driver, ads, extra, g_scan):
    # scroll down the webpage to get all results
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1)
    
    promoted_article_list = process_promoted(driver)

    organic = driver.find_elements(by=By.XPATH, value='//div[@data-cy="search.listing.organic"]')[0]
    organic_article_list = organic.find_elements(by=By.XPATH, value='.//article[@data-cy="listing-item"]')
    article_list = driver.find_elements(by=By.XPATH, value='//article[@data-cy="listing-item"]')
    assert len(article_list) == len(promoted_article_list) + len(organic_article_list)

    l_articles = []
    for article in article_list:
        try:
            links = article.find_elements(by=By.XPATH, value='.//a[@data-cy="listing-item-link"]')
            assert len(links) == 1
            item_prices = article.find_elements(by=By.XPATH, value='.//section/div[2]/div[1]/span')
            assert len(item_prices) == 1
            locs = article.find_elements(by=By.XPATH, value='.//section/div[2]/div[2]/p')
            if len(locs) > 0:
                loc = locs[0]
                address = loc.text
            else:
                address = "[missing]"  # !?
            det = article.find_elements(by=By.XPATH, value='.//section/div[2]/div[3]/dl')[0]
            item_title = article.find_elements(by=By.XPATH, value='.//p[@data-cy="listing-item-title"]')[0]
            img = article.find_elements(by=By.XPATH, value='.//img[@data-cy="listing-item-image-source"]')[0]
            photo = img.get_attribute('src')
            #use scraped data
            url = links[0].get_attribute('href')
            public_id = url.split("-")[-1][2:]
            g_scan['seen_ids'].append(public_id)
            price = item_prices[0].text.replace(" zł", "").replace(" ", "")
            if "€" in price:
                print("--> Pomijam ogłoszenie w Euro", url)
                # could not convert string to float: '115000€'
                # https://www.otodom.pl/pl/oferta/wlasne-mieszkanie-w-turcji-ID4rwNf
                continue
            det_as_list = det.text.split("\n")
            det_as_dict = {k:v for (k,v) in zip(det_as_list[0::2],det_as_list[1::2])}
            #Podbicia
            # up_buttons = article.find_elements(by=By.XPATH, value='.//button[@class="css-wsd8fq e3k5x8s0"]')
            up_buttons = article.find_elements(by=By.XPATH, value='.//section/div[2]/div[5]/div[2]/div/div/button')
            if len(up_buttons) > 1:
                pass
            elif len(up_buttons) > 0:
                up = up_buttons[0]
                #Try scrape up action date
                try_no = 0
                up_text_scraped = False
                while try_no < 3 and not up_text_scraped:
                    try:
                        try_no = try_no + 1
                        ActionChains(driver).move_to_element(up).perform()
                        up_text_el = driver.find_element(by=By.XPATH, value='.//*[ contains (text(), "To ogłoszenie zostało podbite" ) ]')
                        up_text_scraped = True
                    except Exception as e:
                        print(f"Błąd na próbie #{try_no}", e)
                        time.sleep(1)
                if up_text_scraped:
                    up_text = up_text_el.text
                    up_ind = True
                    expr = '(?P<day>\d\d)\.(?P<month>\d\d) o (?P<hour>\d\d)\:(?P<min>\d\d)'
                    match = re.search(expr, up_text)
                    up_datetime = datetime.fromisoformat(f"2024-{match.group('month')}-{match.group('day')}T{match.group('hour')}:{match.group('min')}")
                    up_id = f"{public_id}-{up_datetime.isoformat().replace(':', '_')}"
                    up_dict = {
                        'public_id' : public_id,
                        'up_datetime' : up_datetime.isoformat()
                    }
                    up_filename = f'{UPS_DIR}/up-{up_id}.json'
                    if not os.path.exists(up_filename):
                        with open(up_filename, 'w') as file:
                            file.write(json.dumps(up_dict))
                else:
                    up_text = "Nie"
                    up_ind = False
            else:
                up_text = "Nie"
                up_ind = False
            article_entry = {
                'public_id' : public_id,
                'url' : url,
                'address' : address,
                'title' : item_title.text,
                'photo' : photo,
                'price' : int(float(price.replace(",", "."))),  
                'price_per_square_m' : int(det_as_dict['Cena za metr kwadratowy'].replace(" zł/m²", "").replace(" ", "")),
                'rooms' : det_as_dict['Liczba pokoi'].split(' ')[0],
                'area' : det_as_dict['Powierzchnia'].replace(" m²", ""),
                # 'floor' : det_as_dict['Piętro'],  # TBD ta informacja może nie być dostępna
                # 'podbite' : up_text,
                # 'up_datetime' : up_datetime.isoformat() if up_ind else ""  # datetime.fromtimestamp(0).isoformat()

            }
            l_articles.append(article_entry)
        except Exception as e:
            print("Błąd w scrape(1):", e , " dla ogłoszenia ", url)
            continue
    if len(article_list) == 0:
        pass  # wymagana analiza sytuacji

    for article in l_articles:
        try:
            pid = article['public_id']
            url = article['url']

            price_updated = False
            article_updated = False
            if pid in ads.keys():
                prev_price = ads[pid][-1]['ad']['target']['Price']
                curr_price = article['price']
                price_updated = prev_price != curr_price
                time_passed_since_accessed = datetime.now() - ads[pid][-1]['access_time']
                time_passed_since_modified = datetime.now(tz=zoneinfo.ZoneInfo("Poland")) - datetime.fromisoformat(ads[pid][-1]['ad']['modifiedAt'])
                ad_as_article = ad_to_article_entry(ads[pid][-1]['ad'])
                d = diff(ad_as_article, article)
                del d['address']  # TBD
                article_updated = len(d.keys()) > 0
                if article_updated or article_updated:
                    print('--> Wykryto zmiany', d)
                    if 'title' in d.keys() and not 'url' in d.keys():  # nieistotna zmiana tytułu(?)
                        print('Poprzedni tytuł: ' + ad_as_article['title'])
                        del d['title']
                        if len(d.keys()) == 0:
                            print('Pomijam nieistotną zmianę w tytule dla ', url)
                            continue
                    if price_updated:
                        print(f"--> Nastąpiła zmiana ceny z {prev_price} na {curr_price}!!!")
                elif not ads[pid][-1]['hasCenoskop'] and time_passed_since_modified > timedelta(days=1) \
                    and time_passed_since_accessed > timedelta(hours=2):
                    print(f"Going for cenoskop min/max prices after {time_passed_since_modified}")
                elif pid in extra.keys() and (\
                    (extra[pid][-1]['access_time'] < ads[pid][-1]['access_time'] + timedelta(days=2)\
                    and datetime.now() > extra[pid][-1]['access_time'] + timedelta(days=1))\
                    or datetime.now() > extra[pid][-1]['access_time'] + timedelta(days=7)):
                    time_since_cenoskop_accessed = datetime.now() - extra[pid][-1]['access_time']
                    print(f'Refreshing cenoskop data after {time_since_cenoskop_accessed}')
                else:
                    print("Skipping url " + url)
                    continue
            print(f"Following url {url}")
            driver.get(url)
            g_scan['visited_ids'].append(pid)
            scrape_single(driver=driver, ads=ads, price_updated=price_updated, article_updated=article_updated)
            driver.back()
            time.sleep(2)
            try:
                process_promoted(driver)
            except Exception as e:
                print("Błąd w process_promoted()", e, " dla ogłoszenia", url)
        except Exception as e:
            print("Błąd w scrape(2)", e , " dla ogłoszenia", url)
            continue

    # click on the next button
    time.sleep(2)
    # next_button = driver.find_element(by=By.XPATH, value='//button[@data-cy="pagination.next-page"]')
    # next_button = driver.find_element(by=By.XPATH, value='//li[@class="css-gd4dj2"]')
    next_button = driver.find_element(by=By.XPATH, value='//li[@aria-label="Go to next Page"]')
    
    driver.execute_script("arguments[0].click();", next_button)
    time.sleep(4)

def otodom_main(driver, website):
    driver.maximize_window()
    driver.get(website)

    time.sleep(2)

    # clicking through the accept cookies button
    cookies_button = driver.find_element(by=By.XPATH, value='//button[@id="onetrust-accept-btn-handler"]')
    cookies_button.click()

    time.sleep(2)

    # get total number of results
    # total = driver.find_element(by=By.XPATH, value='//strong[@data-cy="search.listing-panel.label.ads-number"]')
    # total_num = re.findall(r'\d+', total.text)
    # calculate the number of pages
    # num_of_pages = round(int(total_num[0]) / 72)
    pages = driver.find_element(by=By.XPATH, value='//ul[@data-cy="frontend.search.base-pagination.nexus-pagination"]')
    pages_num = re.findall(r'\d+', pages.text)
    num_of_pages = int(pages_num[-1])

    # initiate lists to store data
    location = []
    prices = []
    m2_price = []
    rooms = []
    m2 = []
    urls = []
    publicIds = []

    new_counter = 0
    cenoskop_counter = 0

    ads = read_ads_from_dir()
    extra = read_ads_extra()
    g_promoted = []  # TBD

    for candidate in ['poznan', 'wroclaw']:
                if candidate in website:
                    city = candidate
    g_scan = {
        'started' : datetime.now().isoformat(),
        'city' : city,
        'website' : website,
        'state' : 'STARTED',
        'seen_ids' : [],
        'visited_ids' : [],
    }
    def save_scan(scan):
        city = scan['city']
        scan_filename = f"scan-{city}-{scan['started'].replace(':', '_')}.json"
        with open(f'{SCAN_DIR}/{scan_filename}', 'w') as file:
                file.write(json.dumps(scan))
    save_scan(g_scan)

    # run the function on each page
    i = 1
    while i <= num_of_pages:
        print('Working on page ' + str(i) + ' of ' + str(num_of_pages))
        try:
            scrape(driver, ads, extra, g_scan)
        except Exception as e:
            # print error code
            print(e)
            pass
        i += 1
        save_scan(g_scan)

    g_scan['state'] = 'COMPLETED'
    g_scan['completed'] = datetime.now().isoformat()
    save_scan(g_scan)

    check_inactive(driver, ads, g_scan)