from flask import Flask, request, jsonify , redirect
from flask_cors import CORS
import stripe
import os
import traceback
import requests
from scheduler import start_scheduler
import logging

app = Flask(__name__)
CORS(app)  # Allow all origins by default
# Stripe Secret Key from environment variable
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
# Set your Airtable credentials
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = 'song_requests_tbl'
AIRTABLE_API_URL = f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}'
HEADERS = {
    'Authorization': f'Bearer {AIRTABLE_API_KEY}',
    'Content-Type': 'application/json'
}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Start the scheduler on app startup
start_scheduler()

@app.route("/", methods=["GET"])
def home():
    return "Stripe SetupIntent API is live!"


@app.route('/create-song-request-record', methods=['POST'])
def create_request():
    try:
        # Check that environment variables are set
        if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
            raise EnvironmentError("Missing Airtable API credentials in environment.")

        data = request.json

        # Extract form fields
        request_id = data.get('request_id')
        song_name = data.get('song_name')
        artist_name = data.get('artist_name')
        bid_amount = data.get('bid_amount')
        phone_number = data.get('phone_number')
        requestor_name = data.get('requestor_name')
        shoutout_message = data.get('shoutout_message')

        # Validate required fields
        if not all([request_id, song_name, bid_amount, phone_number]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Attempt to convert bid_amount to float
        try:
            bid_amount = float(bid_amount)
        except ValueError:
            return jsonify({'error': 'Invalid bid_amount. Must be a number.'}), 400

        # Prepare Airtable payload
        airtable_data = {
            'fields': {
                'request_id': request_id,
                'song_name': song_name,
                'artist_name': artist_name,
                'bid_amount': bid_amount,
                'phone_number': phone_number,
                'requestor_name': requestor_name,
                'shoutout_message': shoutout_message
            }
        }

        # Log values for debugging
        print("Posting to Airtable:")
        print("URL:", AIRTABLE_API_URL)
        print("Headers:", HEADERS)
        print("Payload:", airtable_data)

        # Send request to Airtable
        response = requests.post(AIRTABLE_API_URL, json=airtable_data, headers=HEADERS)

        # Raise error if response is not OK
        response.raise_for_status()

        record_id = response.json().get('id')
        return jsonify({'message': 'Request created successfully', 'record_id': record_id}), 200

    except requests.exceptions.RequestException as e:
        print("Airtable API error:")
        traceback.print_exc()
        return jsonify({'error': 'Airtable API error', 'details': str(e)}), 500

    except Exception as e:
        print("General error:")
        traceback.print_exc()
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@app.route('/create-gig-record', methods=['POST'])
def create_gig():
    gigs_tbl_name = 'gigs_tbl'
    AIRTABLE_API_URL_GIGS = f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{gigs_tbl_name}'
    try:
        # Check that environment variables are set
        if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
            raise EnvironmentError("Missing Airtable API credentials in environment.")

        data = request.json

        # Extract form fields
        gig_id = data.get('gig_id')
        dj_name = data.get('dj_name')
        venue = data.get('venue')
        city = data.get('city')
        state = data.get('state')

        # Validate required fields
        if not all([gig_id, venue, city, state]):
            return jsonify({'error': 'Missing required fields'}), 400

        #Generate unique form url for DJ
        generated_form_url = f'https://tally.so/r/wvKEk4?gig_id={gig_id}&dj_name={dj_name}&venue={venue}&city={city}&state={state}'
        
        #Generate qr code url from dj url
        qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?data={generated_form_url}&size=200x200"

        # Prepare Airtable payload
        airtable_data = {
            'fields': {
                'gig_id': gig_id,
                'venue': venue,
                'city': city,
                'state': state,
                'gig_url': qr_code_url
            }
        }

        # Log values for debugging
        print("Posting to Airtable:")
        print("URL:", AIRTABLE_API_URL_GIGS)
        print("Headers:", HEADERS)
        print("Payload:", airtable_data)

        # Send request to Airtable
        response = requests.post(AIRTABLE_API_URL_GIGS, json=airtable_data, headers=HEADERS)

        # Raise error if response is not OK
        response.raise_for_status()

        record_id = response.json().get('id')
        return jsonify({'message': 'Request created successfully', 'record_id': record_id}), 200

    except requests.exceptions.RequestException as e:
        print("Airtable API error:")
        traceback.print_exc()
        return jsonify({'error': 'Airtable API error', 'details': str(e)}), 500

    except Exception as e:
        print("General error:")
        traceback.print_exc()
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@app.route('/update-request-record', methods=['POST'])
def update_request_record():
    try:
        data = request.json
        record_id = data.get('record_id')
        customer_id = data.get('customer_id')
        payment_method_id = data.get('payment_method_id')

        if not record_id or not customer_id or not payment_method_id:
            return jsonify({"error": "Missing required fields"}), 400

        airtable_update_url = f"{AIRTABLE_API_URL}/{record_id}"
        payload = {
            "fields": {
                "customer_id": customer_id,
                "payment_method_id": payment_method_id,
                "card on file": "YES✅"
            }
        }

        response = requests.patch(airtable_update_url, json=payload, headers=HEADERS)
        response.raise_for_status()

        return jsonify({"message": "Record updated successfully"}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Failed to update Airtable", "details": str(e)}), 500


@app.route('/create-payment-intent', methods=['POST'])
def create_payment_intent():
    data = request.get_json()
    request_id = data.get('request_id')
    phone_number = data.get('phone_number')
    connected_account_id = data.get('connect_id')

    if not request_id or not connected_account_id:
        return jsonify({"error": "Missing request_id or connect_id"}), 400

    try:
        # Step 1: Create Stripe Customer (optional but recommended)
        customer = stripe.Customer.create(
            metadata={"request_id": request_id, "phone_number": phone_number}
        )
        
        # Step 2: Create the PaymentIntent for the $0.50 fee
        payment_intent = stripe.PaymentIntent.create(
            amount=50,  # $0.50 in cents (stripe minimum)
            currency="usd",
            customer=customer.id,
            setup_future_usage="off_session",  # Allows for later charge
            metadata={"request_id": request_id},
            payment_method_configuration="pmc_1R87WWAk57lRlYLjs1ZdwkyH",
            automatic_payment_methods={"enabled": True},
            transfer_data={
                "destination": connected_account_id,
                "amount": 40  # 80% of 50 cents
            }
        )

        # Step 3: Return the info to Make
        return jsonify({
            "client_secret": payment_intent.client_secret,
            "payment_intent_id": payment_intent.id,
            "customer_id": customer.id
        })

    except Exception as e:
        print("❌ Exception caught in /create-payment-intent")
        traceback.print_exc()  #
        return jsonify({"error": str(e)}), 500


#once bid is accepted customer is charged full amount
@app.route('/charge-customer', methods=['POST'])
def charge_customer():
    data = request.json
    customer_id = data.get('customer_id')
    payment_method_id = data.get('payment_method_id')
    bid_amount = data.get('bid_amount')  # In dollars or cents depending on your frontend
    request_id = data.get('request_id')
    # field will be removed after adding gig id
    connected_account_id = data.get('dj_connect_id')  # ⬅️ Add this field

    if not all([customer_id, payment_method_id, bid_amount, connected_account_id]):
        return jsonify({'error': 'Missing data'}), 400

    try:
        # Convert bid amount to cents (if it's a float/dollar value)
        bid_amount_cents = int(round(float(bid_amount) * 100))

        # Calculate 20% platform fee
        platform_fee_cents = int(bid_amount_cents * 0.20)

        # Create the off-session charge with transfer to connected account
        payment_intent = stripe.PaymentIntent.create(
            amount=bid_amount_cents,
            currency='usd',
            customer=customer_id,
            payment_method=payment_method_id,
            off_session=True,
            confirm=True,
            metadata={'request_id': request_id},
            application_fee_amount=platform_fee_cents,
            transfer_data={
                'destination': connected_account_id
            }
        )

        return jsonify({'status': 'success', 'payment_intent': payment_intent.id})

    except stripe.error.CardError as e:
        print("❌ Exception caught in /charge-customer")
        traceback.print_exc() 
        return jsonify({'status': 'failed', 'error': str(e)}), 402
    except Exception as e:
        print("❌ Exception caught in /charge-customer")
        traceback.print_exc() 
        return jsonify({'status': 'failed', 'error': str(e)}), 500




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
