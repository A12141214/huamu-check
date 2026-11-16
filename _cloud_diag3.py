from selenium import webdriver
import time
URL = "https://huamu-check-cpedfhcudsasunffkj3a7x.streamlit.app/"
o = webdriver.EdgeOptions(); o.add_argument("--headless=new"); o.add_argument("--window-size=1500,1200")
d = webdriver.Edge(options=o)
try:
    d.get(URL); time.sleep(10)
    srcs = d.execute_script("return Array.from(document.querySelectorAll('iframe')).map(f=>f.src)")
    for s in srcs: print("iframe:", s[:110])
    for idx in range(len(srcs)):
        d.switch_to.default_content()
        d.switch_to.frame(idx)
        info = d.execute_script("return {ta: document.querySelectorAll('textarea').length, b: document.querySelectorAll('button').length, len: document.body.innerText.length}")
        print(f"  frame{idx}: {info}")
finally:
    d.quit()
