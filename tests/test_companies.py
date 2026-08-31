from fastapi.testclient import TestClient


def test_company_crud(client: TestClient) -> None:
    create_response = client.post(
        "/companies",
        json={
            "name": "Example Ltd",
            "website": "https://example.com",
            "privacy_email": "privacy@example.com",
        },
    )
    assert create_response.status_code == 201
    company = create_response.json()
    assert company["name"] == "Example Ltd"

    list_response = client.get("/companies")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    update_response = client.patch(
        f"/companies/{company['id']}",
        json={"notes": "Controller for example account"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["notes"] == "Controller for example account"

    delete_response = client.delete(f"/companies/{company['id']}")
    assert delete_response.status_code == 204

    missing_response = client.get(f"/companies/{company['id']}")
    assert missing_response.status_code == 404

