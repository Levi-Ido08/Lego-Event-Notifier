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
RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL', 'levi0080@gmail.com').strip()

def send_email(updates_list, is_new=True):
    msg = MIMEMultipart()
    msg['Subject'] = 'עדכון חדש: אירועי לגו - שינוי בסטטוס הרשמה' if not is_new else 'עדכון חדש: אירועי לגו חדשים'
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL

    body = '<div dir="rtl" style="text-align: right; font-family: Arial, sans-serif;">'
    body += 'התגלו העדכונים הבאים באירועי הלגו:<br><br>'

    for event in updates_list:
        body += f"כותרת: {event['title']}<br>"
        body += f"תאריכים: {event['dates']}<br>"
        body += f"סטטוס הרשמה: <b>{event['registration_status']}</b><br>"
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
                title = title_tag.get_text(strip=True)

                # --- כניסה לעמוד הפנימי לבדיקת סטטוס ההרשמה ---
                registration_status = 'לא ידוע'
                sub_page = browser.new_page()
                try:
                    sub_page.goto(link, wait_until='networkidle')
                    sub_page_content = sub_page.content()
                    sub_soup = BeautifulSoup(sub_page_content, 'html.parser')
                    
                    page_text = sub_soup.get_text()
                    
                    # בדיקה לפי הטקסטים שהופיעו בצילומי המסך
                    if 'ההרשמה לאירוע תיפתח בקרוב' in page_text:
                        registration_status = 'ההרשמה תיפתח בקרוב (סגור)'
                    elif 'אימות מספר טלפון' in page_text or 'מספר טלפון נייד' in page_text:
                        registration_status = 'ההרשמה פתוחה!'
                    else:
                        registration_status = 'סטטוס לא ברור'
                except Exception as e:
                    print(f'שגיאה בבדיקת העמוד הפנימי של {title}: {e}')
                finally:
                    sub_page.close()

                events.append({
                    'title': title,
                    'link': link,
                    'dates': dates,
                    'description': description,
                    'registration_status': registration_status
                })

        browser.close()
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
    print('Checking for Lego events updates and registration status...')
    current_events = get_events_list()
    cached_events = load_cache()

    # המרה למילון שנוח לחפש לפיו לפי לינק
    cached_dict = {e['link']: e for e in cached_events}

    new_events = []
    status_changed_events = []

    for event in current_events:
        link = event['link']
        if link not in cached_dict:
            # אירוע חדש לגמרי שלא היה בזיכרון
            new_events.append(event)
        else:
            # אירוע קיים - נבדוק האם סטטוס ההרשמה השתנה
            old_status = cached_dict[link].get('registration_status')
            current_status = event['registration_status']
            
            if old_status != current_status:
                print(f"שינוי סטטוס באירוע '{event['title']}': מ-'{old_status}' ל-'{current_status}'")
                status_changed_events.append(event)

    # טיפול באירועים חדשים
    if new_events:
        print(f'>>> Found {len(new_events)} new events! <<<')
        send_email(new_events, is_new=True)

    # טיפול באירועים קיימים שהסטטוס שלהם השתנה (למשל נפתחה ההרשמה)
    if status_changed_events:
        print(f'>>> Found {len(status_changed_events)} events with status changes! <<<')
        send_email(status_changed_events, is_new=False)

    if not new_events and not status_changed_events:
        print('No New Events or Status Changes Found.')

    # שומרים תמיד את המצב העדכני בקש
    save_cache(current_events)


if __name__ == '__main__':
    main()
