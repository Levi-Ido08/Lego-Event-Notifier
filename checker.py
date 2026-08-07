
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL = 'https://lego-events.upsite.dev/events'
CACHE_FILE = 'events_cache.json'

SENDER_EMAIL = os.getenv('SENDER_EMAIL', 'levido08@gmail.com').strip()
IDO_APP_PASSWORD = os.getenv('IDO_APP_PASSWORD', '').strip()
RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL', 'levido08@gmail.com').strip()

def send_email(new_events):
  msg = MIMEMultipart()
  msg['Subject'] = 'עדכון חדש: אירועי לגו'
  msg['From'] = SENDER_EMAIL
  msg['To'] = RECEIVER_EMAIL

  body = '<div dir="rtl" style="text-align: right; font-family: Arial, sans-serif;">'
  body += 'נמצאו אירועים חדשים:<br><br>'

  for event in new_events:
    body += f"כותרת: {event['title']}<br>"
    body += f"תאריכים: {event['dates']}<br>"
    body += f"תיאור: {event['description']}<br>"
    body += f"לינק: {event['link']}<br><br>"
    body += '-' * 30 + '<br>'

  body += '</div>'

  msg.attach(MIMEText(body, 'html', 'utf-8'))

  try:
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
      server.starttls()
      server.login(SENDER_EMAIL, IDO_APP_PASSWORD)
      server.send_message(msg)
    print('המייל נשלח בהצלחה!')
  except Exception as e:
    print(f'שגיאה בשליחת המייל: {e}')

def get_events_list():
  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    page.goto(URL, wait_until='networkidle')
    html_content = page.content()
    browser.close()

  soup = BeautifulSoup(html_content, 'html.parser')
  event_cards = soup.select('li.event-card.group')

  events = []
  for card in event_cards:
    link_tag = card.find('a', href=True)
    title_tag = card.find('h3')
    date_tag = card.find('time')
    description_tag = card.find('div', class_='event-description')

    if link_tag and title_tag:
      link = link_tag['href']
      if link.startswith('/'):
        link = 'https://lego-events.upsite.dev' + link

      dates = ''
      if date_tag:
        span_date = date_tag.find('span')
        dates = (
            span_date.get_text(strip=True)
            if span_date
            else date_tag.get_text(strip=True)
        )

      description = description_tag.get_text(strip=True) if description_tag else ''

      events.append({
          'title': title_tag.get_text(strip=True),
          'link': link,
          'dates': dates,
          'description': description,
      })

  return events


def load_cache():
  if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
      return json.load(f)
  return []


def save_cache(events):
  with open(CACHE_FILE, 'w', encoding='utf-8') as f:
    json.dump(events, f, ensure_ascii=False, indent=4)


def main():
  print('Checking for Lego events updates...')
  current_events = get_events_list()
  cached_events = load_cache()

  cached_links = {e['link'] for e in cached_events}
  new_events = [e for e in current_events if e['link'] not in cached_links]

  if new_events:
    print(f'>>> Found {len(new_events)} new events! <<<')
    for event in new_events:
      print(f"Title: {event['title']}")
      print(f"Dates: {event['dates']}")
      print(f"Description: {event['description']}")
      print(f"Link: {event['link']}\n")

    send_email(new_events)
    save_cache(current_events)
  else:
    print('No New Events Found.')


if __name__ == '__main__':
  main()
