from flask import Flask, request, jsonify , redirect
from flask_cors import CORS
import stripe
import os
import traceback
import requests

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

@app.route("/", methods=["GET"])
def home():
    return "Stripe SetupIntent API is live!"


@app.route('/create-song-request-record', methods=['POST'])
def create_request():
    data = request.json

    # Extract form fields
    song_name = data.get('song_name')
    artist_name = data.get('artist_name')
    bid_amount = data.get('bid_amount')
    phone_number = data.get('phone_number')
    requestor_name = data.get('requestor_name')
    shoutout_message = data.get('shoutout_message')

    # Validate
    if not all([song_name, bid_amount, phone_number]):
        return jsonify({'error': 'Missing required fields'}), 400

    # Prepare Airtable data
    airtable_data = {
        'fields': {
            'song_name': song_name,
            'artist_name': artist_name,
            'bid_amount': float(bid_amount),
            'phone_number': phone_number,
            'requestor_name': requestor_name,
            'shoutout_message': shoutout_message
        }
    }

    # Send to Airtable
    response = requests.post(AIRTABLE_API_URL, json=airtable_data, headers=HEADERS)

    if response.status_code == 200:
        record_id = response.json().get('id')
        return jsonify({'message': 'Request created successfully', 'record_id': record_id}), 200
    else:
        return jsonify({'error': 'Failed to create record', 'details': response.text}), 500


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
    payment_method_id = data.get('bid_payment_method_id')
    bid_amount = data.get('bid_amount')  # In dollars or cents depending on your frontend
    request_id = data.get('request_id')
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
