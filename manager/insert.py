import os
import streamlit as st
import sqlite3
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

from search.safe import escape_special_characters

GOOGLE_SAFE_BROWSING_API_KEY = os.environ.get('GSB_API_KEY')

allowed_extensions = {"http", "https"}

def content_exists(conn, link):
    with conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT COUNT(*) FROM information WHERE link = ?''', (link,))
        count = cursor.fetchone()[0]
        return count > 0

def is_content_safe(link):
    url = 'https://safebrowsing.googleapis.com/v4/threatMatches:find?key=' + str(GOOGLE_SAFE_BROWSING_API_KEY)
    payload = {
        "client": {
            "clientId": "your-client-id",
            "clientVersion": "1.5.2"
        },
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": link}]
        }
    }
    headers = {
        'Content-Type': 'application/json'
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code == 200:
        data = response.json()
        if 'matches' in data and data['matches']:
            return False
    return True

def insert_data(conn, link, title, text, description, keywords, shorttext):
    title = escape_special_characters(title)
    text = escape_special_characters(text)
    description = escape_special_characters(description)
    keywords = escape_special_characters(keywords)
    shorttext = escape_special_characters(shorttext)

    added = datetime.now()

    cursor = conn.cursor()
    cursor.execute("SELECT MAX(site_id) FROM information")
    max_site_id = cursor.fetchone()[0]
    if max_site_id is None:
        site_id = 1
    else:
        site_id = max_site_id + 1

    try:
        response = requests.get(link)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        text_content = "\n".join([p.text for p in soup.find_all('p')])
    except requests.RequestException as e:
        return "Error accessing or parsing the website."

    if content_exists(conn, link):
        return "Content already exists in the database."

    if not is_content_safe(link):
        return "Unsafe content detected. Not inserting into the database."

    with conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''INSERT INTO information 
                              (site_id, link, title, text, description, keywords, shorttext, added) 
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                           (site_id, link, title, text, description, keywords, shorttext, added))
            conn.commit()
            cursor.close()
            return "Data inserted successfully."
        except sqlite3.Error as e:
            cursor.close()
            return "Error inserting data into the database:", e
