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
        phone = data.get("phone_number")
        song_name = data.get("song_name")
        timestamp = data.get("timestamp")

        # Create customer (optional fields passed as metadata)
        customer = stripe.Customer.create(
            metadata={
                "request_id": req_id,
                "song_name": song_name,
                "timestamp": timestamp
            },
            phone=phone
        )

        # Create SetupIntent
        setup_intent = stripe.SetupIntent.create(
            customer=customer.id,
            payment_method_types=['card']
        )

        return jsonify({
            "customer_id": customer.id,
            "setup_intent_client_secret": setup_intent.client_secret
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
