from flask import Flask, request, jsonify , redirect
import stripe
import os

app = Flask(__name__)

# Stripe Secret Key from environment variable
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@app.route("/", methods=["GET"])
def home():
    return "Stripe SetupIntent API is live!"

@app.route("/setup-intent", methods=["POST"])
def setup_intent():
    try:
        # Parse JSON payload from Zapier/Form
        data = request.json
        req_id = data.get("request_id")
        email = data.get("email")
        song_name = data.get("song_name")
        timestamp = data.get("timestamp")
        bid_amount = data.get("bid_amount")  # e.g., $8.00 if passed in
        dj_stripe_connect_id = data.get("stripe_account_id")
        request_fee_cents = 50  # $0.50
        #convert json from string to float
        bid_amount_float = float(bid_amount)
        #convert bid amount to cents
        bid_amount_cents = int(round(bid_amount_float * 100))
        
        
        # Step 1: Create Stripe Customer
        customer = stripe.Customer.create(
            email=email,  # Optional — only if you want to show this in Stripe dashboard
            metadata={
                "request_id": req_id,
                "song_name": song_name,
                "timestamp": timestamp
            }
        )

        # Step 3: Create PaymentIntent to charge request fee
        fee_intent = stripe.PaymentIntent.create(
            amount=request_fee_cents,
            currency='usd',
            customer=customer.id,
            application_fee_amount=int(round(request_fee_cents * 0.20)), # 20% of 50 cents = 10 cents
            automatic_payment_methods={"enabled": True},
            setup_future_usage="off_session",  # ← THIS SAVES THE CARD TOO
            transfer_data={
                "destination":  dj_stripe_connect_id # <-- You must pass DJ's Connect account ID
            }
        )

        return jsonify({
            "fee_payment_intent_client_secret": fee_intent.client_secret,
            "customer_id": customer.id,
            "bid_amount": bid_amount_cents
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/start-checkout', methods=['GET'])
def start_checkout():
    request_id = request.args.get('request_id')
    connected_account_id = request.args.get('connect_id')
    if not request_id:
        return jsonify({"error": "Missing request_id"}), 400

    try:
        # Create a Stripe customer and attach metadata
        customer = stripe.Customer.create(
            metadata={
                "request_id": request_id
            }
        )

        # Create a Checkout Session for the bid fee (e.g., $0.50)
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "Song Request Fee"},
                    "unit_amount": 50  # $0.50 in cents
                },
                "quantity": 1
            }],
            customer=customer.id,
            payment_intent_data={
                "setup_future_usage": "off_session",  # ✅ This is the correct placement
                "metadata": {
                    "request_id": request_id
                },
                "transfer_data": {
                    "destination": connected_account_id,
                    "amount": 40  # 80% of $0.50 = $0.40 (in cents)
                }
            },
            success_url="https://tally.so/r/mev0Qe",
            cancel_url="https://tally.so/r/3qvYWY"
        )

        return redirect(checkout_session.url)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/store-payment-method", methods=["POST"])
def store_payment_method():
    try:
        data = request.json
        request_id = data.get("request_id")
        customer_id = data.get("customer_id")
        payment_method_id = data.get("payment_method_id")

        # TODO: Replace this with your logic to store values in Airtable or a database
        print("✅ Received payment method for storage:")
        print("Request ID:", request_id)
        print("Customer ID:", customer_id)
        print("Payment Method ID:", payment_method_id)

        return jsonify({"status": "success"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

#once bid is accepted customer is charged full amount
@app.route('/charge-customer', methods=['POST'])
def charge_customer():
    data = request.json
    customer_id = data.get('customer_id')
    payment_method_id = data.get('bid_payment_method_id')
    bid_amount = data.get('bid_amount')  # in cents
    request_id = data.get('request_id')
    
     #convert json from string to float
    bid_amount_float = float(bid_amount)
    #convert bid amount to cents
    bid_amount_cents = int(round(bid_amount_float * 100))

    if not all([customer_id, payment_method_id,bid_amount_cents]):
        return jsonify({'error': 'Missing data'}), 400

    try:
        # Create the charge
        payment_intent = stripe.PaymentIntent.create(
            amount=bid_amount_cents,
            currency='usd',
            customer=customer_id,
            payment_method=payment_method_id,
            off_session=True,
            confirm=True,
            metadata={'request_id': request_id}
        )
        return jsonify({'status': 'success', 'payment_intent': payment_intent.id})
    except stripe.error.CardError as e:
        return jsonify({'status': 'failed', 'error': str(e)}), 402
    except Exception as e:
        return jsonify({'status': 'failed', 'error': str(e)}), 500



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
