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
VIEW_NAME = 'accepted_view'
CLICKSEND_API_KEY = os.getenv("CLICKSEND_API_KEY")
CLICKSEND_USERNAME = os.getenv("CLICKSEND_USERNAME")
CHARGE_CUSTOMER_URL = 'https://stripe-intent-python-script.onrender.com/charge-customer'

HEADERS = {
    'Authorization': f'Bearer {AIRTABLE_API_KEY}',
    'Content-Type': 'application/json'
}

def get_accepted_unnotified_records():
    url = f'https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}'
    params = {
        'view': VIEW_NAME,
        'filterByFormula': 'OR({notified} = 0, NOT({notified}))'
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

def lookup_connect_id_by_gig_id(gig_id):
    """
    Helper function to lookup the DJ's Stripe connect ID based on gig_id.
    """
    search_url = f"https://api.airtable.com/v0/{BASE_ID}/gigs_tbl"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    params = {
        "filterByFormula": f"gig_id='{gig_id}'",
        "maxRecords": 1
    }

    response = requests.get(search_url, headers=headers, params=params)
    response.raise_for_status()

    records = response.json().get('records', [])
    if not records:
        raise ValueError(f"No gig found for gig_id: {gig_id}")

    fields = records[0]['fields']
    connect_id = fields.get('stripe_connect_id')

    if not connect_id:
        raise ValueError(f"No stripe_connect_id found for gig_id: {gig_id}")

    return connect_id


def check_and_notify():
    logging.info("Running check_and_notify task...")

    try:
        records = get_accepted_unnotified_records()
        if not records:
            logging.info("No new accepted records to process.")
            return

        for record in records:
            fields = record['fields']
            record_id = record['id']
            phone = fields.get('phone_number')
            song = fields.get('song_name')
            customer_id = fields.get('customer_id')
            payment_method_id = fields.get('payment_method_id')
            bid_amount = fields.get('bid_amount')  # e.g. "2.50"
            request_id = fields.get('request_id')
            gig_id = fields.get('gig_id')  # 🆕 We now use gig_id from the song request record

            if not all([phone, song, customer_id, payment_method_id, bid_amount, request_id, gig_id]):
                logging.warning(f"Missing data for record {record_id}, skipping.")
                continue

            # 🆕 Lookup DJ connect ID dynamically
            try:
                dj_connect_id = lookup_connect_id_by_gig_id(gig_id)
            except Exception as e:
                logging.error(f"Failed to lookup connect ID for gig_id {gig_id}: {e}")
                continue

            # Step 1: Attempt to charge the customer
            try:
                payload = {
                    "customer_id": customer_id,
                    "payment_method_id": payment_method_id,
                    "bid_amount": bid_amount,
                    "request_id": request_id,
                    "dj_connect_id": dj_connect_id
                }
                charge_response = requests.post(CHARGE_CUSTOMER_URL, json=payload)
                charge_response.raise_for_status()
                logging.info(f"Charged customer {customer_id} for request {request_id}")
            except Exception as e:
                logging.error(f"Charge failed for customer {customer_id}, request {request_id}: {e}")
                continue  # Skip SMS and update if charge failed

            # Step 2: Send SMS after successful charge
            try:
                send_sms_notification(phone, song)
                logging.info(f"SMS sent to {phone} for song '{song}'")
            except Exception as e:
                logging.error(f"Failed to send SMS to {phone}: {e}")
                continue  # Skip update if SMS fails

            # Step 3: Mark record as notified
            try:
                mark_as_notified(record_id)
                logging.info(f"Record {record_id} marked as notified.")
            except Exception as e:
                logging.error(f"Failed to mark record {record_id} as notified: {e}")

    except Exception as e:
        logging.error(f"Error during scheduled check: {e}")
