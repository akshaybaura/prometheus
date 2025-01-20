from flask import Flask, Response
import random
app = Flask(__name__)

@app.route('/metrics')
def metrics():
    random_value = random.uniform(0, 200)
    content = f"""example_metric{{label=\"test\"}} {random_value:.2f}"""
    return Response(content, mimetype="text/plain")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
