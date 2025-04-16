import requests
from datetime import datetime, timezone
import logging
import os
import clicksend_client
from clicksend_client import SmsMessage
from clicksend_client.rest import ApiException

# Airtable setup
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE_NAME = 'song_requests_tbl'
VIEW_NAME = 'Accepted'
CLICKSEND_API_KEY = os.getenv("CLICKSEND_API_KEY")
CLICKSEND_USERNAME = os.getenv("CLICKSEND_USERNAME")

HEADERS = {
    'Authorization': f'Bearer {AIRTABLE_API_KEY}',
    'Content-Type': 'application/json'
}

def get_accepted_unnotified_records():
    url = f'https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}'
    params = {
        'view': VIEW_NAME,
        'filterByFormula': "NOT({notified})"
    }

    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    records = response.json().get('records', [])
    logging.info(f"Found {len(records)} unnotified accepted records.")
    return records


def send_sms_notification(phone_number, song_title):
    configuration = clicksend_client.Configuration()
    configuration.username = CLICKSEND_USERNAME
    configuration.password = CLICKSEND_API_KEY

    api_instance = clicksend_client.SMSApi(clicksend_client.ApiClient(configuration))

    message = SmsMessage(
        source="python",
        body=f"Your song request for '{song_title}' has been accepted! Stick close to the dance floor it's playing soon!",
        to=phone_number,
        custom_string="NxtSong"
    )

    sms_messages = clicksend_client.SmsMessageCollection(messages=[message])

    try:
        response = api_instance.sms_send_post(sms_messages)
        print(f"SMS sent to {phone_number}: {response}")
    except ApiException as e:
        print(f"ClickSend SMS failed: {e}")

def mark_as_notified(record_id):
    url = f'https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}/{record_id}'
    data = {
        "fields": {
            "notified": True,
            "notified_at": datetime.now(timezone.utc).isoformat()
        }
    }

    response = requests.patch(url, headers=HEADERS, json=data)
    response.raise_for_status()
    logging.info(f"Marked record {record_id} as notified.")

def check_and_notify():
    logging.info("Running check_and_notify task...")

    try:
        records = get_accepted_unnotified_records()
        for record in records:
            fields = record['fields']
            phone = fields.get('phone_number')
            song = fields.get('song_name')
            record_id = record['id']

            if phone and song:
                send_sms_notification(phone, song)
                mark_as_notified(record_id)
            else:
                logging.warning(f"Missing phone or song for record {record_id}")
    except Exception as e:
        logging.error(f"Error during scheduled check: {e}")
