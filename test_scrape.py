import requests
from bs4 import BeautifulSoup
import traceback

def check_isyatirim(ticker):
    url = f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={ticker}"
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Look for Foreign Ratio (Yabancı Oranı)
        # IsYatirim usually has a table with "Yabancı Oranı (%)"
        table = soup.find('table', {'id': 'tblMaliTablo'})
        print(f"IsYatirim fetch for {ticker} status: {r.status_code}")
        # print snippet
        if r.status_code == 200:
            print("Successfully loaded page.")
            # find text containing "Yabancı"
            for td in soup.find_all('td'):
                if 'Yabancı' in td.text or 'yabancı' in td.text.lower():
                    print(td.text.strip(), td.find_next_sibling('td').text.strip() if td.find_next_sibling('td') else '')
    except Exception as e:
        traceback.print_exc()

check_isyatirim('TOASO')
