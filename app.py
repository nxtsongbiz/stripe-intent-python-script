from flask import Flask, request, jsonify
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

        # Step 2: Create SetupIntent to save card
        setup_intent = stripe.SetupIntent.create(
            customer=customer.id,
            payment_method_types=["card","cashapp"]
        )
        
        # Step 3: Create PaymentIntent to charge request fee
        fee_intent = stripe.PaymentIntent.create(
            amount=request_fee_cents,
            currency='usd',
            customer=customer.id,
            payment_method_types=["card","cashapp"],
            application_fee_amount=int(round(request_fee_cents * 0.20)),  # 20% of 50 cents = 10 cents
            transfer_data={
                "destination":  dj_stripe_connect_id # <-- You must pass DJ's Connect account ID
            }
        )

        return jsonify({
            "setup_intent_client_secret": setup_intent.client_secret,
            "fee_payment_intent_client_secret": fee_intent.client_secret,
            "customer_id": customer.id,
            "bid_amount": bid_amount_cents
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
