from selenium import webdriver
from selenium.webdriver.common.by import By
import time
URL = "https://huamu-check-cpedfhcudsasunffkj3a7x.streamlit.app/"
o = webdriver.EdgeOptions(); o.add_argument("--headless=new"); o.add_argument("--window-size=1400,1000")
o.set_capability("goog:loggingPrefs", {"browser": "ALL"})
d = webdriver.Edge(options=o)
try:
    d.get(URL); time.sleep(12)
    d.save_screenshot("_cloud_diag.png")
    print("title:", d.title[:60])
    txt = d.find_element(By.TAG_NAME, "body").text
    print("可见文字（前 500 字）:")
    print((txt[:500] or "(空)").replace("\n"," | "))
    print("--- 控制台 ---")
    for e in d.get_log("browser")[:8]:
        print("  ", e["level"], e["message"][:120])
finally:
    d.quit()
