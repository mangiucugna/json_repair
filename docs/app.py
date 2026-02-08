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
        malformed_json = data.get("malformedJSON")
        if not isinstance(malformed_json, str):
            raise ValueError("malformedJSON must be a string.")

        schema = data.get("schema")
        if schema is not None and not isinstance(schema, (dict, bool)):
            raise ValueError("schema must be a JSON object or boolean.")

        # Repair the malformed JSON
        loads_kwargs = {"logging": True}
        if schema is not None:
            loads_kwargs["schema"] = schema
        parsed_json = loads(malformed_json, **loads_kwargs)

        return jsonify(parsed_json)
    except (BadRequest, TypeError, ValueError) as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    app.run()
