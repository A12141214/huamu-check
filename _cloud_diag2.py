from selenium import webdriver
from selenium.webdriver.common.by import By
import time
URL = "https://huamu-check-cpedfhcudsasunffkj3a7x.streamlit.app/"
o = webdriver.EdgeOptions(); o.add_argument("--headless=new"); o.add_argument("--window-size=1500,1200")
d = webdriver.Edge(options=o)
try:
    d.get(URL)
    for t in (10, 25, 45):
        time.sleep(t if t==10 else 15)
        info = d.execute_script("""
            return {
              ready: document.readyState,
              textareas: document.querySelectorAll('textarea').length,
              buttons: document.querySelectorAll('button').length,
              iframes: document.querySelectorAll('iframe').length,
              bodyLen: document.body.innerText.length,
              title: document.title
            };""")
        print(f"{t}s:", info)
finally:
    d.quit()
