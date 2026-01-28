from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import BadRequest

from json_repair import loads

app = Flask(__name__)
CORS(app)  # This will enable CORS for all routes


@app.route("/api/repair-json", methods=["POST"])
def format_json():
    try:
        data = request.get_json()
        if not isinstance(data, dict):
            raise ValueError("Request JSON must be an object.")
        malformed_json = data["malformedJSON"]

        # Repair the malformed JSON
        parsed_json = loads(malformed_json, logging=True)

        return jsonify(parsed_json)
    except (BadRequest, KeyError, TypeError, ValueError) as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    app.run()
