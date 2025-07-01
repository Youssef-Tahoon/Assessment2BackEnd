from flask import Flask, render_template
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
import time
import re
import os

app = Flask(__name__)


def extract_date_from_url(url):
    """Extract date from URL patterns like /2024/12/31/ or /2024/12/31/article-title"""
    date_patterns = [
        r'/(\d{4})/(\d{1,2})/(\d{1,2})/',  # /2024/12/31/
        r'/(\d{4})-(\d{1,2})-(\d{1,2})',   # /2024-12-31
        r'/(\d{4})/(\d{1,2})/(\d{1,2})$',  # /2024/12/31
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, url)
        if match:
            try:
                year, month, day = map(int, match.groups())
                if 2020 <= year <= 2024 and 1 <= month <= 12 and 1 <= day <= 31:
                    return datetime(year, month, day)
            except (ValueError, TypeError):
                continue
    return None


def scrape():
    base_url = "https://www.theverge.com/"
    articles = []
    cutoff = datetime(2022, 1, 1)
    
    # Add headers to mimic a real browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        # Try the main page first
        resp = requests.get(base_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"Failed to fetch main page: {resp.status_code}")
            return articles

        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Try multiple selectors for article entries
        selectors = [
            "div.c-compact-river__entry",
            "article.c-entry-box",
            "div.c-entry-box",
            "article",
            "div[data-chorus-optimization-id]",
            "div.c-entry-box--compact",
            "div.c-entry-box--compact__body"
        ]
        
        entries = []
        for selector in selectors:
            entries = soup.select(selector)
            if entries:
                print(f"Found {len(entries)} entries using selector: {selector}")
                break
        
        if not entries:
            print("No articles found with any selector")
            # Try to find any links that might be articles
            all_links = soup.find_all('a', href=True)
            article_links = []
            for link in all_links:
                href = link.get('href')
                if href and isinstance(href, str) and ('/20' in href or '/202' in href):
                    article_links.append(link)
            
            print(f"Found {len(article_links)} potential article links")
            
            for link in article_links[:30]:  # Limit to first 30
                title = link.get_text(strip=True)
                if title and len(title) > 10:  # Only consider meaningful titles
                    href = link.get('href')
                    if href and isinstance(href, str):
                        full_url = urljoin(base_url, href)
                        
                        # Extract date from URL
                        date = extract_date_from_url(full_url)
                        if not date:
                            # Skip articles without a clear date
                            continue
                        
                        # Only add if from 2022 onwards
                        if date >= cutoff:
                            articles.append({
                                'title': title,
                                'link': full_url,
                                'date': date
                            })
            
            return articles

        for entry in entries[:50]:  # Limit to first 50 entries
            try:
                # Try multiple ways to find title and link
                title = None
                link = None
                
                # Method 1: Look for h2 with title class
                h2 = entry.find("h2", class_="c-entry-box--compact__title")
                if h2:
                    a = h2.find("a")
                    if a:
                        title = a.get_text(strip=True)
                        href = a.get('href')
                        if href and isinstance(href, str):
                            link = urljoin(base_url, href)
                
                # Method 2: Look for any h2 or h3
                if not title:
                    for tag in ['h2', 'h3', 'h1']:
                        title_tag = entry.find(tag)
                        if title_tag:
                            a = title_tag.find("a")
                            if a:
                                title = a.get_text(strip=True)
                                href = a.get('href')
                                if href and isinstance(href, str):
                                    link = urljoin(base_url, href)
                                break
                
                # Method 3: Look for any link with meaningful text
                if not title:
                    links = entry.find_all("a")
                    for a in links:
                        text = a.get_text(strip=True)
                        if text and len(text) > 10 and not text.startswith('http'):
                            title = text
                            href = a.get('href')
                            if href and isinstance(href, str):
                                link = urljoin(base_url, href)
                            break
                
                if not title or not link:
                    continue
                
                # Try to find publication date
                date = None
                
                # Method 1: Look for time tag with datetime attribute
                time_tag = entry.find("time")
                if time_tag and hasattr(time_tag, 'get') and time_tag.get("datetime"):
                    try:
                        date_str = time_tag.get("datetime").rstrip('Z')
                        date = datetime.fromisoformat(date_str)
                    except:
                        pass
                
                # Method 2: Extract date from URL
                if not date:
                    date = extract_date_from_url(link)
                
                # Method 3: Look for date in text content
                if not date:
                    # Look for date patterns in the entry text
                    entry_text = entry.get_text()
                    date_patterns = [
                        r'(\d{4})-(\d{1,2})-(\d{1,2})',  # 2024-12-31
                        r'(\d{1,2})/(\d{1,2})/(\d{4})',  # 12/31/2024
                        r'(\d{4})/(\d{1,2})/(\d{1,2})',  # 2024/12/31
                    ]
                    
                    for pattern in date_patterns:
                        match = re.search(pattern, entry_text)
                        if match:
                            try:
                                if pattern == r'(\d{1,2})/(\d{1,2})/(\d{4})':
                                    month, day, year = map(int, match.groups())
                                else:
                                    year, month, day = map(int, match.groups())
                                
                                if 2020 <= year <= 2024 and 1 <= month <= 12 and 1 <= day <= 31:
                                    date = datetime(year, month, day)
                                    break
                            except (ValueError, TypeError):
                                continue
                
                # Skip articles without a clear date or older than cutoff
                if not date or date < cutoff:
                    continue
                
                articles.append({
                    'title': title,
                    'link': link,
                    'date': date
                })
                    
            except Exception as e:
                print(f"Error processing entry: {e}")
                continue
        
        # Sort newest first (anti-chronologically)
        articles.sort(key=lambda x: x['date'], reverse=True)
        print(f"Successfully scraped {len(articles)} articles from 2022 onwards")
        
    except Exception as e:
        print(f"Error during scraping: {e}")
    
    return articles


@app.route('/')
def index():
    articles = scrape()
    return render_template('index.html', articles=articles)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)