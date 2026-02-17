import pytest

pytest.importorskip("flask")

from docs.app import app


@pytest.fixture
def client():
    app.testing = True
    with app.test_client() as test_client:
        yield test_client


def test_docs_api_without_schema_keeps_existing_behavior(client):
    response = client.post(
        "/api/repair-json",
        json={"malformedJSON": '{"value": "1"}'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == [{"value": "1"}, []]


def test_docs_api_schema_null_is_treated_as_missing(client):
    response = client.post(
        "/api/repair-json",
        json={"malformedJSON": '{"value": "1"}', "schema": None},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == [{"value": "1"}, []]


def test_docs_api_schema_guides_coercion(client):
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
    }

    response = client.post(
        "/api/repair-json",
        json={"malformedJSON": '{"value": "1"}', "schema": schema},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    assert payload[0] == {"value": 1}
    assert isinstance(payload[1], list)
    assert payload[1]


def test_docs_api_rejects_invalid_schema_type(client):
    response = client.post(
        "/api/repair-json",
        json={"malformedJSON": '{"value": "1"}', "schema": []},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "schema must be a JSON object or boolean."}


def test_docs_api_schema_validation_error_returns_400(client):
    pytest.importorskip("jsonschema")
    response = client.post(
        "/api/repair-json",
        json={
            "malformedJSON": '"bbb"',
            "schema": {"type": "string", "pattern": "^a+$"},
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "error" in payload
    assert "does not match" in payload["error"]


def test_docs_api_rejects_invalid_schema_repair_mode_type(client):
    response = client.post(
        "/api/repair-json",
        json={"malformedJSON": '{"value": "1"}', "schemaRepairMode": True},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "schemaRepairMode must be a string."}


def test_docs_api_rejects_invalid_schema_repair_mode_value(client):
    response = client.post(
        "/api/repair-json",
        json={"malformedJSON": '{"value": "1"}', "schemaRepairMode": "unknown"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "schemaRepairMode must be 'standard' or 'salvage'."}


def test_docs_api_rejects_salvage_mode_without_schema(client):
    response = client.post(
        "/api/repair-json",
        json={"malformedJSON": '{"value": "1"}', "schemaRepairMode": "salvage"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "schemaRepairMode='salvage' requires schema."}


def test_docs_api_salvage_mode_drops_invalid_array_items(client):
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "score": {"type": "number"},
                    },
                    "required": ["id", "score"],
                },
            }
        },
        "required": ["items"],
    }

    response = client.post(
        "/api/repair-json",
        json={
            "malformedJSON": '{"items":[{"id":1,"score":85.6},{"id":2,"score":"N/A"}]}',
            "schema": schema,
            "schemaRepairMode": "salvage",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    assert payload[0] == {"items": [{"id": 1, "score": 85.6}]}
