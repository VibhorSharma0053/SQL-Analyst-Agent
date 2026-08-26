# file: tests/test_api.py

"""
Integration tests for the FastAPI endpoints.

These tests use httpx.TestClient to make HTTP requests to the
FastAPI app without starting a real server. This is fast and
does not require a running uvicorn process.

Run: pytest tests/test_api.py -v
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


# Create a test client. This is like a fake browser that
# sends HTTP requests to the FastAPI app in-process.
client = TestClient(app)


class TestHealthEndpoint:
    """Test the GET /health endpoint."""

    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_json(self):
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_has_version(self):
        response = client.get("/health")
        data = response.json()
        assert "version" in data


class TestSchemaEndpoint:
    """Test the GET /schema endpoint."""

    def test_schema_returns_200(self):
        response = client.get("/schema")
        assert response.status_code == 200

    def test_schema_contains_tables(self):
        response = client.get("/schema")
        data = response.json()
        assert "schema_text" in data
        assert "customers" in data["schema_text"]
        assert "products" in data["schema_text"]
        assert "orders" in data["schema_text"]
        assert "order_items" in data["schema_text"]

    def test_schema_raw_mode(self):
        response = client.get("/schema?raw=true")
        data = response.json()
        assert "customers" in data
        assert "products" in data


class TestCustomersEndpoint:
    """Test the GET /customers endpoint."""

    def test_customers_returns_200(self):
        response = client.get("/customers")
        assert response.status_code == 200

    def test_customers_returns_list(self):
        response = client.get("/customers")
        data = response.json()
        assert "customers" in data
        assert "count" in data
        assert data["count"] == 20

    def test_customer_has_required_fields(self):
        response = client.get("/customers")
        customer = response.json()["customers"][0]
        assert "customer_id" in customer
        assert "name" in customer
        assert "email" in customer
        assert "city" in customer


class TestAnalyzeEndpoint:
    """
    Test the POST /analyze endpoint.

    Note: These tests call the real LLM (Ollama) if the /analyze
    endpoint triggers AI generation. For fast CI testing, you may
    want to mock the LLM. For now, we test input validation which
    does not need the LLM.
    """

    def test_analyze_rejects_empty_question(self):
        response = client.post(
            "/analyze",
            json={"question": "   "},
        )
        assert response.status_code == 422

    def test_analyze_rejects_short_question(self):
        response = client.post(
            "/analyze",
            json={"question": "hi"},
        )
        assert response.status_code == 422

    def test_analyze_rejects_missing_question(self):
        response = client.post(
            "/analyze",
            json={},
        )
        assert response.status_code == 422

    def test_analyze_rejects_non_json(self):
        response = client.post(
            "/analyze",
            content="not json",
            headers={"Content-Type": "text/plain"},
        )
        assert response.status_code == 422

    def test_analyze_response_shape(self):
        """
        Test that a valid request returns the correct response shape.
        This test calls the real LLM, so it may be slow.
        Skip it in CI by setting the environment variable SKIP_LLM=1.
        """
        import os
        if os.environ.get("SKIP_LLM"):
            pytest.skip("Skipping LLM test (SKIP_LLM=1)")

        response = client.post(
            "/analyze",
            json={"question": "How many customers do we have?"},
        )
        assert response.status_code == 200
        data = response.json()

        # Verify all expected fields exist
        assert "question" in data
        assert "answer" in data
        assert "sql" in data
        assert "columns" in data
        assert "rows" in data
        assert "row_count" in data
        assert "truncated" in data
        assert "warnings" in data
        assert "error" in data


class TestSecurityEndpoints:
    """
    Test that the API does not expose sensitive information.
    """

    def test_health_does_not_expose_api_key(self):
        response = client.get("/health")
        text = response.text.lower()
        assert "sk-" not in text
        assert "api_key" not in text
        assert "password" not in text

    def test_schema_does_not_expose_secrets(self):
        response = client.get("/schema")
        text = response.text.lower()
        assert "password" not in text
        assert "secret" not in text
        assert "credential" not in text