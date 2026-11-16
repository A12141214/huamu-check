from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
URL = "https://huamu-check-cpedfhcudsasunffkj3a7x.streamlit.app/"
SAMPLE = "家人们看这棵桂花，四季开花，养死包赔，全网最低价，喜欢的赶紧下单！"
o = webdriver.EdgeOptions(); o.add_argument("--headless=new"); o.add_argument("--window-size=1500,1500")
d = webdriver.Edge(options=o)
try:
    d.get(URL)
    WebDriverWait(d, 90).until(lambda x: x.execute_script("return document.querySelectorAll('iframe').length") > 0)
    time.sleep(5)
    d.switch_to.frame(0)
    box = WebDriverWait(d, 120).until(EC.presence_of_element_located((By.TAG_NAME, "textarea")))
    print("应用就绪")
    box.click(); box.send_keys(SAMPLE); time.sleep(1)
    for b in d.find_elements(By.TAG_NAME, "button"):
        if "开始校验" in (b.text or ""):
            b.click(); print("已点校验"); break
    WebDriverWait(d, 240).until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'命中条数')]")))
    time.sleep(12)
    print("指标:", [e.text for e in d.find_elements(By.CSS_SELECTOR, "[data-testid='stMetricValue']")])
    body = d.find_element(By.TAG_NAME, "body").text
    print("出现改写建议:", "DeepSeek 改写建议" in body)
    print("仍提示未配置Key:", "未配置 DEEPSEEK_API_KEY" in body)
    print("出现401:", "401" in body)
    d.save_screenshot("_cloud_final.png")
finally:
    d.quit()
