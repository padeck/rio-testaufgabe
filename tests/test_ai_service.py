from app import ai_service


def test_incident_example_is_critical_and_matches_task_spec():
    result = ai_service.classify_rule_based(
        "Seit heute Morgen ist das Produktivsystem nicht erreichbar."
    )
    assert result.category == "incident"
    assert result.priority == "critical"
    assert result.assigned_team == "platform-operations"
    assert ai_service.compute_status(result.category, result.priority) == "manual_review_required"


def test_account_lockout_example_is_account_access_high():
    result = ai_service.classify_rule_based(
        "Mein Benutzerkonto ist gesperrt und ich kann mich nicht anmelden."
    )
    assert result.category == "account_access"
    assert result.priority == "high"
    assert result.assigned_team == "identity-operations"
    assert ai_service.compute_status(result.category, result.priority) == "open"


def test_how_to_billing_example_is_low_priority_and_open():
    result = ai_service.classify_rule_based(
        "Wie kann ich meine Rechnungsadresse ändern?"
    )
    assert result.priority == "low"
    assert result.category in ("billing", "how_to")
    assert ai_service.compute_status(result.category, result.priority) == "open"


def test_unclassifiable_text_falls_back_to_general_medium():
    result = ai_service.classify_rule_based("asdf qwer zxcv")
    assert result.category == "general"
    assert result.priority == "medium"
    assert result.assigned_team == "first-level-support"


def test_analyze_uses_simulated_tier_when_no_api_key():
    result = ai_service.analyze("Das System ist nicht erreichbar, produktiv kritisch.")
    assert result.analysis_method == "simulated"
