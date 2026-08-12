FORBIDDEN_PHRASES = ["diagnosis", "recommended treatment", "you have", "probability of disease"]


def test_api_responses_avoid_clinical_diagnostic_language(client, seeded_biomed_db) -> None:
    response = client.get("/api/v1/conditions/MONDO:0007915")
    text = response.text.lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in text
