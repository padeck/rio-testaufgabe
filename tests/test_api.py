def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_and_get_ticket_roundtrip(client):
    create_resp = client.post(
        "/api/tickets",
        json={"request": "Seit heute Morgen ist das Produktivsystem nicht erreichbar."},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()

    assert body["category"] == "incident"
    assert body["priority"] == "critical"
    assert body["assignedTeam"] == "platform-operations"
    assert body["status"] == "manual_review_required"
    assert body["analysisMethod"] == "simulated"
    assert body["ticketId"].startswith("T-")

    get_resp = client.get(f"/api/tickets/{body['ticketId']}")
    assert get_resp.status_code == 200
    assert get_resp.json() == body


def test_get_unknown_ticket_is_404(client):
    resp = client.get("/api/tickets/T-doesnotexist")
    assert resp.status_code == 404


def test_create_ticket_rejects_empty_request(client):
    resp = client.post("/api/tickets", json={"request": ""})
    assert resp.status_code == 422


def test_list_tickets_filters_by_status(client):
    client.post("/api/tickets", json={"request": "Wie kann ich meine Rechnungsadresse ändern?"})
    resp = client.get("/api/tickets", params={"status": "manual_review_required"})
    assert resp.status_code == 200
    body = resp.json()
    assert all(t["status"] == "manual_review_required" for t in body["tickets"])
