from fastapi.testclient import TestClient


def test_account_crud(client: TestClient) -> None:
    company_response = client.post("/companies", json={"name": "Example Ltd"})
    assert company_response.status_code == 201
    company_id = company_response.json()["id"]

    create_response = client.post(
        "/accounts",
        json={
            "company_id": company_id,
            "label": "Primary account",
            "account_identifier": "user@example.com",
        },
    )
    assert create_response.status_code == 201
    account = create_response.json()
    assert account["label"] == "Primary account"

    list_response = client.get("/accounts")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    update_response = client.patch(f"/accounts/{account['id']}", json={"notes": "Personal login"})
    assert update_response.status_code == 200
    assert update_response.json()["notes"] == "Personal login"

    delete_response = client.delete(f"/accounts/{account['id']}")
    assert delete_response.status_code == 204

    missing_response = client.get(f"/accounts/{account['id']}")
    assert missing_response.status_code == 404


def test_account_requires_existing_company(client: TestClient) -> None:
    response = client.post(
        "/accounts",
        json={"company_id": 999, "label": "Missing company account"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Company not found"

