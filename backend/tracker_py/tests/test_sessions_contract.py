from app.main import app


def test_session_search_allows_bounded_analytics_history():
    parameters = app.openapi()["paths"]["/sessions/search"]["get"]["parameters"]
    limit = next(parameter for parameter in parameters if parameter["name"] == "limit")

    assert limit["schema"]["default"] == 200
    assert limit["schema"]["minimum"] == 1
    assert limit["schema"]["maximum"] == 5000
