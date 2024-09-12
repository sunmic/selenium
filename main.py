from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os

import requests
external_ip = requests.get("https://api.ipify.org/").text
print(f"Connecting from {external_ip}")

from otodom import *

# initiate the chrome driver and declare the url
website = os.getenv('WEBSITE')
print(website)

driver = gen_driver()
otodom_main(driver, website)


#close the browser
driver.quit()
