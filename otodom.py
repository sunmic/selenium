import os
from dotenv import load_dotenv

load_dotenv()

DATA_DIR =  os.getenv('DATA_DIR')
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

import pymongo
PRIMARY_CONNECTION_STRING = os.getenv('PRIMARY_CONNECTION_STRING')
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME')
mongo_client = pymongo.MongoClient(PRIMARY_CONNECTION_STRING)
mongo_db = mongo_client[MONGO_DB_NAME]

USE_MONGO_DICT = ('y' == os.getenv('USE_MONGO_DICT', 'n'))

class MongoDict:

    def __init__(self, collection, connection_string=PRIMARY_CONNECTION_STRING):
        self.client = pymongo.MongoClient(connection_string)
        self.db = self.client[MONGO_DB_NAME]
        self.collection = self.db[collection]
        self.collection_key = f'{collection}.public_id' if collection in ['promo', 'up'] else f'{collection}.publicId'
        self.collection.create_index({self.collection_key : 1})
        self.collection.create_index({'access_time' : 1})  # required for CosmosDB for MongoDB  
        # https://stackoverflow.com/questions/56988743/using-the-sort-cursor-method-without-the-default-indexing-policy-in-azure-cosm

    def __getitem__(self, key):
        list = [x for x in self.collection.find({self.collection_key : key}, {'_id' : 0}).sort({'access_time' : 1})]
        return list
    
    def __len__(self):
        return len(self.collection.distinct(self.collection_key))
    
    def __contains__(self, key):
        return self.collection.find_one({self.collection_key: key}) is not None
    
    def __iter__(self):
        return iter(self.collection.distinct(self.collection_key))
    
    def keys(self):
        return self.__iter__()
    
    def items(self):
        return map(lambda x : (x, self.__getitem__(x)), self.__iter__())

USE_HEADLESS_MODE = ('y' == os.getenv('USE_HEADLESS_MODE', 'n'))

def gen_driver(headless=USE_HEADLESS_MODE):
    if not headless:
        from selenium import webdriver
        driver = webdriver.Chrome()
        return driver
    else:
        print("Using HEADLESS mode")
        # https://stackoverflow.com/questions/68289474/selenium-headless-how-to-bypass-cloudflare-detection-using-selenium
        import undetected_chromedriver as uc
        from selenium_stealth import stealth
        try:
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.140 Safari/537.36"
            chrome_options = uc.ChromeOptions()
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("user-agent={}".format(user_agent))
            driver = uc.Chrome(options=chrome_options)
            stealth(driver,
                    languages=["en-US", "en"],
                    vendor="Google Inc.",
                    platform="Win32",
                    webgl_vendor="Intel Inc.",
                    renderer="Intel Iris OpenGL Engine",
                    fix_hairline=True
            )
            return driver
        except Exception as e:
            print("Error in Driver: ",e)

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
        if public_id not in ups:
            ups[public_id] = []
        ups[public_id].append(entry)
    
    for public_id in ups:
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
        if public_id not in promo:
            promo[public_id] = []
        promo[public_id].append(entry)
    
    for public_id in promo:
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
        if public_id not in extra:
            extra[public_id] = []
        extra[public_id].append(entry)
    
    for public_id in extra:
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
                        # 'hasCenoskop' : prefix_fun(filename) in other_dir_prefixes, # obsolete
                        'expired' : directory == EXPIRED_DIR
                        }
        if public_id not in ads:
            ads[public_id] = []
        ads[public_id].append(entry)

    for public_id in ads:
        ads[public_id] = sorted(ads[public_id], key = lambda x : x['access_time'])
    
    count = len(ads)
    print(f"Loading of {count} ads finished.")
    return ads

def save_document_fs(directory, name, content):
    if '.json' != name[-5:]:
        name += '.json'  # add '.json' suffix if not present
    path = f'{directory}/{name}'

    if not os.path.exists(path):
        with open(path, 'w') as file:
                file.write(json.dumps(content))

def save_document_mongo(directory, name, content, key):
    if '.json' == name[-5:]:
        name = name[:-5]  # remove '.json' suffix if present
    if key in ['up', 'promo']:
        access_time = datetime.fromisoformat('-'.join(name.split('-')[2:]).replace('_', ':'))
    else:
        access_time = datetime.fromtimestamp(int(name.split('-')[2]))
    document = {
        'access_time' : access_time,
        'entry_name' : name,
        key : content,
        'directory' : directory.split('/')[-1]
    }
    if key == 'ad':
        document['expired'] = (directory == EXPIRED_DIR)
    
    if mongo_db[key].count_documents({'entry_name': document['entry_name']}, limit = 1) > 0:
        return
    mongo_db[key].insert_one(document=document)

def save_document(directory, name, content, key):
    save_document_fs(directory, name, content)
    save_document_mongo(directory, name, content, key)

def scrape_single(driver, ads, price_updated=False, article_updated=False):
    title = driver.title
    while '404' in driver.title[:40] or 'ERROR' in driver.title:
        print(driver.title)
        time.sleep(20)
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
    if public_id == '':
        url = ad.get('url')
        public_id = url.split("-")[-1]
        assert public_id[:2] == 'ID'
        public_id = public_id[2:]
        ad['publicId'] = public_id
    ad_id = str(ad.get('id')) + '-' + public_id + '-' + str(int(time.time()))

    if public_id in ads:
        None # print(f"Already has basic data for {public_id}")
        prev_date = ads[public_id][-1]['ad']['modifiedAt']
        this_date = ad['modifiedAt']
        modified = this_date != prev_date
        if article_updated != modified:
            None # breakpoint position
        if price_updated or article_updated or modified:
            save_document(directory=ADS_UPDATE_DIR, name=ad_id, content=ad, key='ad')
            if not USE_MONGO_DICT:
                ads[public_id].append({'access_time' : datetime.now(),
                            'ad' : ad
                            })  # sort not needed as time flows forward
    else:
        save_document(directory=NEXT_DATA_DIR, name=ad_id, content=jsontext, key='next_data')
        if not USE_MONGO_DICT:
            ads[public_id] = [{'access_time' : datetime.now(),
                            'ad' : ad
                            }]
        save_document(directory=ADS_DIR, name=ad_id, content=ad, key='ad')
    
    if is_expired:
        if not USE_MONGO_DICT:
            ads[public_id].append({'access_time' : datetime.now(),
                        'ad' : ad
                        })  # sort not needed as time flows forward
        save_document(directory=EXPIRED_DIR, name=ad_id, content=ad, key='ad')

    # if len(min_price_value) > 0 and (not ads[public_id][-1]['hasCenoskop'] or price_updated or article_updated):
    if len(min_price_value) > 0:
        other = {
                        "id"        : ad.get('id'),
                        "publicId"  : ad.get('publicId'),
                        "min_price" : min_price_value[0].replace(" zł", "").replace(" ", ""),
                        "max_price" : max_price_value[0].replace(" zł", "").replace(" ", "")
                    }
        save_document(directory=OTHER_DIR, name=ad_id, content=other, key='extra')    

        # print("Gathered cenoskop min/max prices.")
    elif not is_expired:
        print("Missing cenoskop min/max prices!")

def process_promoted(driver):
        promoted_l = driver.find_elements(by=By.XPATH, value='//div[@data-cy="search.listing.promoted"]')
        while (len(promoted_l) == 0):
            time.sleep(2)
            print("--> Próba przywrócenia strony z wynikami (refresh/back)")
            print(driver.current_url)
            print(driver.title)
            if 'ERROR' in driver.title:
                time.sleep(20)
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

            name=f"promo-{public_id}-{entry['promo_date']}"
            promo_filename = f"{PROMO_DIR}/{name}.json"
            save_document(directory=PROMO_DIR, name=name, content=entry, key='promo')
        return promoted_article_list

def check_inactive(driver, ads, scan):
    assert scan['state'] == 'COMPLETED'
    
    if 'city' in scan:
        city = scan['city']
    else:
        for candidate in ['poznan', 'wroclaw', 'katowice']:
            if candidate in scan['website']:
                city = candidate
    
    if USE_MONGO_DICT:
        ads.collection.create_index({'ad.target.City' : 1})
        ads.collection.create_index({'directory' : 1})
        ads.collection.create_index({'ad.target.City' : 1, 'directory' : 1})
        city_ids = [ad['ad']['publicId'] for ad in ads.collection.find({'ad.target.City' : city}, 
                                                                       {'ad.publicId' : 1})]
        expired_ids = [ad['ad']['publicId'] for ad in ads.collection.find({'ad.target.City' : city,
                                                                           'directory' : EXPIRED_DIR.split('/')[-1]},
                                                                           {'ad.publicId' : 1})]
    else:
        city_ids = [k for (k,v) in ads.items() if v[-1]['ad']['target']['City'] == city]
        public_id_fun = lambda x : x.split('-')[1]
        expired_ids = [public_id_fun(x) for x in os.listdir(EXPIRED_DIR)]

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
    while '404' in driver.title[:40] or 'ERROR' in driver.title:
        print(driver.title)
        time.sleep(20)
        driver.refresh()
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
                if USE_HEADLESS_MODE:
                    print("Wyłączone zbieranie podbić z powodu trybu headless")
                while try_no < 3 and not up_text_scraped and not USE_HEADLESS_MODE:
                    try:
                        try_no = try_no + 1
                        ActionChains(driver).move_to_element(up).perform()
                        up_text_el = driver.find_element(by=By.XPATH, value='.//*[ contains (text(), "To ogłoszenie zostało podbite" ) ]')  # TBD: Fails in headless mode !!!
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
                    name = f"up-{up_id}"
                    save_document(directory=UPS_DIR, name=name, content=up_dict, key='up')
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
            print(driver.title)
            continue
    if len(article_list) == 0:
        pass  # wymagana analiza sytuacji

    for article in l_articles:
        try:
            pid = article['public_id']
            url = article['url']

            price_updated = False
            article_updated = False
            if pid in ads:
                prev_price = ads[pid][-1]['ad']['target']['Price']
                curr_price = article['price']
                price_updated = prev_price != curr_price
                time_passed_since_accessed = datetime.now() - ads[pid][-1]['access_time']
                time_passed_since_modified = datetime.now(tz=zoneinfo.ZoneInfo("Poland")) - datetime.fromisoformat(ads[pid][-1]['ad']['modifiedAt'])
                ad_as_article = ad_to_article_entry(ads[pid][-1]['ad'])
                d = diff(ad_as_article, article)
                del d['address']  # TBD
                article_updated = len(d) > 0
                if article_updated or article_updated:
                    print('--> Wykryto zmiany', d)
                    if 'title' in d and not 'url' in d:  # nieistotna zmiana tytułu(?)
                        print('Poprzedni tytuł: ' + ad_as_article['title'])
                        del d['title']
                        if len(d) == 0:
                            print('Pomijam nieistotną zmianę w tytule dla ', url)
                            continue
                    if price_updated:
                        print(f"--> Nastąpiła zmiana ceny z {prev_price} na {curr_price}!!!")
                elif not pid in extra and time_passed_since_modified > timedelta(days=1) \
                    and time_passed_since_accessed > timedelta(hours=2):
                    print(f"Going for cenoskop min/max prices after {time_passed_since_modified}")
                elif pid in extra and (\
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
            print(driver.title)
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
    if 'ERROR' in driver.title:
        print(driver.current_url)
        print(driver.title)
        return

    # clicking through the accept cookies button
    if not USE_HEADLESS_MODE:
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

    if USE_MONGO_DICT:
        print("Using MongoDict for 'ad' and 'extra'")
        ads = MongoDict('ad')
        extra = MongoDict('extra')
        print('Ads:', len(ads))
        print('Extra:', len(extra))
    else:
        ads = read_ads_from_dir()
        extra = read_ads_extra()
    g_promoted = []  # TBD

    for candidate in ['poznan', 'wroclaw', 'katowice']:
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