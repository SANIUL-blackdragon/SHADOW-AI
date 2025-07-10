from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import json
import os
from datetime import datetime
from webdriver_manager.chrome import ChromeDriverManager

# Configuration
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "scale")
CSV_FILE = os.path.join(OUTPUT_DIR, f"202507{datetime.now().strftime('%d')}.csv")
os.makedirs(OUTPUT_DIR, exist_ok=True)
print(f"Output directory created/verified: {os.path.abspath(OUTPUT_DIR)}")

def setup_driver():
    options = Options()
    options.add_argument("--headless")  # Run in background
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
    return driver

def scrape_price(driver):
    driver.get("https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT")
    time.sleep(5)  # Wait for page load
    try:
        # Update selector based on TradingView's current DOM
        price_element = driver.find_element(By.CSS_SELECTOR, ".last-JWoJqCpY")
        price = float(price_element.text.replace(",", ""))
        return price
    except Exception as e:
        print(f"Error scraping price: {e}")
        return None

def save_data(price):
    if price is None:
        return
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    data = {"ticker": "BINANCE:BTCUSDT", "price": price, "timestamp": timestamp}
    with open(CSV_FILE, 'a', encoding='utf-8') as f:
        if not os.path.exists(CSV_FILE):
            f.write("timestamp,price\n")
        f.write(f"{timestamp},{price}\n")
    print(json.dumps(data))
    return data

def main():
    driver = setup_driver()
    try:
        while True:
            price = scrape_price(driver)
            save_data(price)
            time.sleep(5)
    except KeyboardInterrupt:
        print("Stopping S.C.A.L.E.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()