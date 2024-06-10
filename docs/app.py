from flask import Flask, request, jsonify
from flask_cors import CORS
from json_repair import loads

app = Flask(__name__)
CORS(app)  # This will enable CORS for all routes


@app.route("/api/repair-json", methods=["POST"])
def format_json():
    try:
        data = request.get_json()
        malformed_json = data["malformedJSON"]

        # Repair the malformed JSON
        parsed_json = loads(malformed_json)

        return jsonify(parsed_json)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    app.run()
