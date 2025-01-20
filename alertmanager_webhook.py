from flask import Flask, request

app = Flask(__name__)


@app.route('/alerts', methods=['POST'])
def receive_alerts():
    # Get the JSON payload from Alertmanager
    data = request.json

    # Print the received payload
    print("Received Alert Payload:")
    print(data)

    # Return a success response
    return {"status": "success"}, 200


if __name__ == '__main__':
    # Start the Flask app on localhost, port 5000
    app.run(host='0.0.0.0', port=5000)