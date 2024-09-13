import locale
locale.setlocale(locale.LC_ALL, '')  # for the numeric formatting
import streamlit as st
from otodom import *
from datetime import datetime
import pandas as pd
import copy

@st.cache_resource
def st_read_ads_from_dir():
    return read_ads_from_dir()

@st.cache_resource
def st_read_extra():
    return read_ads_extra()  

if not USE_MONGO_DICT:
    ads = st_read_ads_from_dir()
    extra = st_read_extra()
else:
    print('Using MongoDict for ad, extra, up and promo')
    ads = MongoDict('ad')
    extra = MongoDict('extra')
    ups = MongoDict('up')
    promos = MongoDict('promo')

def reload_callback():
    st.cache_resource.clear()

def f_expired(public_id):
    return ads[public_id][-1]['expired']

def f_poznan(public_id):
    return ads[public_id][-1]['ad']['target']['City'] == 'poznan'

def f_wroclaw(public_id):
    return ads[public_id][-1]['ad']['target']['City'] == 'wroclaw'

def f_geo(public_id, geo=''):
    if ads[public_id][-1]['ad']['location']['reverseGeocoding']['locations'] is None:
        # print(public_id)
        return False
    # return geo in [l['id'] for l in ads[public_id][-1]['ad']['location']['reverseGeocoding']['locations']]
    return any([geo in l['id'] for l in ads[public_id][-1]['ad']['location']['reverseGeocoding']['locations']])

def f_rok_od(public_id):
    return 'Build_year' in ads[public_id][-1]['ad']['target'] \
        and int(ads[public_id][-1]['ad']['target']['Build_year']) > 2000

def f_TBS(public_id):
    return 'TBS' in ads[public_id][-1]['ad']['description']

@st.cache_resource
def cenoskop_idx(extra=extra, ads=ads, geo='dolnoslaskie/wroclaw/wroclaw/wroclaw'):
    print("Calculating cenoskop_idx")
    idx = []
    for public_id in extra:
        if f_expired(public_id) or f_TBS(public_id) or not \
            (f_geo(public_id, geo) and f_rok_od(public_id)):
            # (f_poznan(public_id) and f_rok_od(public_id)):
            continue
        price = int(ads[public_id][-1]['ad']['target']['Price'])
        price_per_m = int(ads[public_id][-1]['ad']['target']['Price_per_m'])
        area = float(ads[public_id][-1]['ad']['target']['Area'])
        
        c_min = int(extra[public_id][-1]['extra']['min_price'])
        c_max = int(extra[public_id][-1]['extra']['max_price'])
        cenoskop_idx = (price - c_min)/(c_max - c_min)

        # cenoskop = pd.DataFrame(dict(
        #     cenoskop_idx = round(cenoskop_idx, 2),
        #     min_price = str(c_min) + " zł",
        #     min_price_per_m = str(round(c_min / area, 2)) + " zł/m²",
        #     max_price = str(c_max) + " zł",
        #     max_price_per_m = str(round(c_max / area, 2)) + " zł/m²"
        # ), index=[''])
        entry = dict(
            public_id=public_id,
            price=price,
            price_per_m=price_per_m,
            area=area,
            min_price=c_min,
            max_price=c_max,
            cenoskop_idx=cenoskop_idx
        )
        idx.append(entry)
    idx = sorted(idx, key = lambda x : x['cenoskop_idx'])
    return idx

with st.sidebar:
    geo = st.text_input('Geo')
    print(f'{123456}')
    st.write(f'{123456}')

idx = cenoskop_idx(geo=geo)
url = ''
if 'url' in st.query_params:
    url = st.query_params['url']
else:
    url = st.text_input("Url:")

with st.sidebar:
    col1, col2 = st.columns([1, 2])
    with col1:
        reload = st.button('Reload', on_click=reload_callback)
    with col2:
        st.write(len(ads))
    
    for i in range(min(25, len(idx))):
        col1, col2 = st.columns([4, 1])
        col1.write(f"{round(idx[i]['cenoskop_idx'],2)} \
                   {idx[i]['price']/1000}k \
                   {idx[i]['area']}m2 \
                   {idx[i]['price_per_m']/1000}k/m2"
                   )
        if col2.button("Go", key=f"but_{i}"):
            url=idx[i]['public_id']
        

def oto_diff(a, b):
    import jsondiff as jd
    from jsondiff import diff
    import difflib
    from bs4 import BeautifulSoup
    from functools import reduce
    import copy
    import base64

    flat_map = lambda f, xs: reduce(lambda a, b: a + b, map(f, xs))

    a = copy.deepcopy(a)
    b = copy.deepcopy(b)

    a['access_time'] = a['access_time'].isoformat()
    b['access_time'] = b['access_time'].isoformat()

    out = diff(a, b)
    
    if 'ad' in out and 'userAdverts' in out['ad']:
        del out['ad']['userAdverts']

    if 'ad' in out and 'target' in out['ad'] and 'Photo' in out['ad']['target']:
        out['ad']['target']['Photo'] = base64.b64decode(out['ad']['target']['Photo']).decode('utf-8')

    if 'ad' in out and 'description' in out['ad']:
        d0 = BeautifulSoup(a['ad']['description'], 'html.parser').get_text().strip().split('\n')
        d1 = BeautifulSoup(b['ad']['description'], 'html.parser').get_text().strip().split('\n')

        split = lambda x : x.strip().replace('. ', '.').replace('.', '.###').split('###')

        d0 = flat_map(split, d0)
        d1 = flat_map(split, d1)

        d0 = [d for d in d0 if len(d) > 0]
        d1 = [d for d in d1 if len(d) > 0]

        c = difflib.Differ()

        diff_desc = '\n'.join([line for line in c.compare(d0, d1) if line[:2] != '  '])

        out['ad']['description'] = diff_desc
    
    if 'ad' in out and 'seo' in out['ad'] and 'description' in out['ad']['seo']:
        d0 = BeautifulSoup(a['ad']['seo']['description'], 'html.parser').get_text().strip().split('\n')
        d1 = BeautifulSoup(b['ad']['seo']['description'], 'html.parser').get_text().strip().split('\n')

        split = lambda x : x.strip().replace('. ', '.').replace('.', '.###').split('###')

        d0 = flat_map(split, d0)
        d1 = flat_map(split, d1)

        d0 = [d for d in d0 if len(d) > 0]
        d1 = [d for d in d1 if len(d) > 0]

        c = difflib.Differ()

        diff_desc = '\n'.join([line for line in c.compare(d0, d1) if line[:2] != '  '])

        out['ad']['seo']['description'] = diff_desc
    
    if 'ad' in out and 'title' in out['ad']:
        # d0 = BeautifulSoup(a['ad']['title'], 'html.parser').get_text().strip().split('\n')
        # d1 = BeautifulSoup(b['ad']['title'], 'html.parser').get_text().strip().split('\n')

        # split = lambda x : x.strip().replace('. ', '.').replace('.', '.###').split('###')

        # d0 = flat_map(split, d0)
        # d1 = flat_map(split, d1)

        # d0 = [d for d in d0 if len(d) > 0]
        # d1 = [d for d in d1 if len(d) > 0]

        d0 = [a['ad']['title']]
        d1 = [b['ad']['title']]

        c = difflib.Differ()

        diff_desc = '\n'.join([line for line in c.compare(d0, d1) if line[:2] != '  '])

        out['ad']['title'] = diff_desc

    return out

if url != '':
    public_id = url.split("-")[-1]
    if public_id[:2] == 'ID':
        public_id = public_id[2:]

    if not USE_MONGO_DICT:  # MongoDict uses online data, no need to refresh
        ads_for_id = read_ads_from_dir(public_id=public_id)
        if public_id in ads_for_id and (not public_id in ads\
            or len(ads_for_id[public_id]) != len(ads[public_id])):
            print("Updated for ", public_id)
            ads[public_id] = ads_for_id[public_id]
        extra_for_id = read_ads_extra(public_id=public_id)
        if public_id in extra_for_id:
            extra[public_id] = extra_for_id[public_id]

    if public_id in ads:
        ad_list = ads[public_id]
        ad_list_rev = copy.copy(ad_list)
        ad_list_rev.reverse()
        
        is_expired = ad_list[-1]['expired']
        if is_expired:
            st.warning('To ogłoszenie jest już niedostępne.', icon=':material/block:')
        
        st.write(ads[public_id][-1]['ad']['url'])
        st.write(ads[public_id][-1]['ad']['location']['reverseGeocoding']['locations'][-1]['id'])

        test_items = [{
            'title': '',
            'text': '',
            'img': img['medium'],
            'link': img['large']
            } for img in ads[public_id][-1]['ad']['images']]

        from streamlit_carousel import carousel
        carousel(items=test_items, width=1)
        
        price = int(ad_list[-1]['ad']['target']['Price'])
        price_per_m = int(ad_list[-1]['ad']['target']['Price_per_m'])
        area = float(ad_list[-1]['ad']['target']['Area'])
        
        # details = pd.DataFrame(dict(
        #     price = str(price) + " zł",
        #     area = str(area) + " m²",
        #     price_per_m=price_per_m
        # ), index=[''])
        # st.table(details.transpose())

        col1, col2 = st.columns(2)
        if public_id in extra:
            c_min = int(extra[public_id][-1]['extra']['min_price'])
            c_max = int(extra[public_id][-1]['extra']['max_price'])
            cenoskop_idx = (price - c_min)/(c_max - c_min)

            
            cenoskop = pd.DataFrame(dict(
                cenoskop_idx = f'{round(cenoskop_idx, 2):n}',
                min_price = f'{c_min:n} zł',
                min_price_per_m = f'{round(c_min / area, 2):n} zł/m²',
                max_price = f'{c_max:n} zł',
                max_price_per_m = f'{round(c_max / area, 2):n} zł/m²'
            ), index=[''])
           
            col1.write("Cenoskop:")
            col1.table(cenoskop.transpose().astype(str))
        else:
            col1.write("Dane z cenoskopu nie są dostępne.")

        col2.write('Zmiany cen:')
        price_hist = [(entry['ad']['modifiedAt'][:10], 
                       entry['ad']['characteristics'][0]['localizedValue'], #entry['ad']['target']['Price'],
                       entry['ad']['characteristics'][2]['localizedValue'], #entry['ad']['target']['Price_per_m']
                       ) for entry in ads[public_id]]
        col2.table(price_hist)
        
        if public_id in extra:
            col2.write('Zmiany cenoskopu:')
            cenoskop_hist = [(entry['access_time'],
                            entry['extra']['min_price'],
                            entry['extra']['max_price'],
                            ) for entry in extra[public_id]]
            col2.table(cenoskop_hist)

        col1, col2 = st.columns(2)

        col1.write("Characteristics")
        characteristics = {e['label'] : e['localizedValue'] for e in ad_list[-1]['ad']['characteristics']}
        col1.table(characteristics)

        # location_ = {'latitude': [ad_list[-1]['ad']['location']['coordinates']['latitude']],
        #     'longitude' : [ad_list[-1]['ad']['location']['coordinates']['longitude']],
        #     'size' : [10]}
        # st.map(location, size='size', zoom=15)
        location = pd.DataFrame(ad_list[-1]['ad']['location']['coordinates'], index=[0])
        radius = ad_list[-1]['ad']['location']['mapDetails']['radius']
        zoom = 15  # ad_list[-1]['ad']['location']['mapDetails']['zoom']
        col2.map(location, size=5+radius, zoom=zoom)
        
        col1, col2 = st.columns(2)
        col1.write("AdditionalInfo/1")
        additional_info = ad_list[-1]['ad']['topInformation']#.extend(ad_list[-1]['ad']['additionalInformation'])
        additional_info_dict = {el['label'] : ','.join(el['values'])+el['unit']
                    for el in additional_info}
        col1.table(additional_info_dict)

        col2.write("AdditionalInfo/2")
        additional_info_2 = ad_list[-1]['ad']['additionalInformation']
        additional_info_dict_2 = {el['label'] : ','.join(el['values'])+el['unit']
                    for el in additional_info_2}
        col2.table(additional_info_dict_2)


        # article = ad_to_article_entry(ads[public_id][-1]['ad'])
        # # st.image(article['photo'])
        # # for (k,v) in article.items():
        # #     st.write(k, v)
        # article_df = pd.DataFrame(article, index=[''])
        # st.table(article_df[['title', 'price', 'price_per_square_m','area', 'rooms']].transpose())
        # st.write(article)

        st.write(ad_list[-1]['ad']['title'])
        html_desc = ad_list[-1]['ad']['description']
        c_desc = st.container(border=True)
        c_desc.markdown(html_desc, unsafe_allow_html=True)

        st.write('Data publikacji: ', datetime.fromisoformat(ad_list[0]['ad']['createdAt']).date())
        st.write('Pierwsza znana wersja: ', datetime.fromisoformat(ad_list[0]['ad']['modifiedAt']).date())
        st.write('Ostatnia znana wersja: ', datetime.fromisoformat(ad_list[-1]['ad']['modifiedAt']).date())

        # count = len(ads[public_id])
        # plural_suffix = 's' if count > 1 else ''
        # st.write(f"Found {count} data point{plural_suffix} for {public_id}.")


        col1, col2 = st.columns(2)
        
        if not USE_MONGO_DICT:
            ups = read_ads_ups(public_id=public_id)
            promos = read_ads_promo(public_id=public_id)
        else:
            pass # MongoDict for up and promo already defined

        if public_id in ups:
            up_times = [datetime.fromisoformat(up['up']['up_datetime']) for up in ups[public_id]]
            st.write('Podbicia:', len(ups[public_id]))
            st.table(up_times)
        else:
            st.write('Brak podbić')      
        
        if public_id in promos:
            promo_times = [date.fromisoformat(promo['promo']['promo_date']) for promo in promos[public_id]]
            st.write('Promowania:', len(promos[public_id]))
            st.table(promo_times)
        else:
            st.write('Brak promowań')

        st.write('Liczba zmian', len(ad_list)-1)
        if len(ad_list) > 1:
            st.write("Historia zmian:")
            for (a,b) in zip(reversed(ad_list[:-1]), reversed(ad_list[1:])):
                st.write('Zmiana z:', datetime.fromisoformat(b['ad']['modifiedAt']).date())
                d = oto_diff(a, b)
                if 'ad' in d and 'target' in d['ad'] and 'Photo' in d['ad']['target']:
                    st.write('zmiana obrazka')
                    col1, sep, col2 = st.columns([14, 1, 14])
                    import base64
                    col1.image(image=base64.b64decode(a['ad']['target']['Photo']).decode('utf-8'))
                    sep.write('->')
                    col2.image(image=base64.b64decode(b['ad']['target']['Photo']).decode('utf-8'))
                else:
                    pass # st.write('bez zmiany obrazka')
                st.write(d)
        st.write('Pierwsza wersja w całości:')
        st.write(ad_list[0])
        
    else:
        st.write(f"No data for {public_id}.")
