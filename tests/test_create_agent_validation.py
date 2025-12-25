import pytest
from unittest.mock import patch, MagicMock
from tools.agent import create_agent

@pytest.fixture
def mock_resp():
    mock = MagicMock()
    mock.status_code = 201
    mock.headers = {"content-type": "application/json"}
    mock.json.return_value = {"id": "agent_test_123", "name": "Test Agent"}
    return mock

@patch("tools.agent.resilient_request")
@patch("tools.agent.default_headers")
def test_create_agent_with_new_parameters(mock_headers, mock_request, mock_resp):
    """
    Test that create_agent can handle projectIds, removeProjectIds, and isCollaborative.
    This test is expected to fail initially (Red Phase) because the parameters are not in the signature.
    """
    mock_headers.return_value = {"Authorization": "Bearer test"}
    mock_request.return_value = mock_resp
    
    # These parameters are currently NOT in the create_agent signature
    result = create_agent(
        name="Test Agent",
        provider="openai",
        model="gpt-4",
        projectIds=["project_1"],
        removeProjectIds=["project_2"],
        isCollaborative=True
    )
    
    assert result["id"] == "agent_test_123"
    
    # Verify that the parameters were passed in the JSON body
    args, kwargs = mock_request.call_args
    sent_json = kwargs["json"]
    assert sent_json["projectIds"] == ["project_1"]
    assert sent_json["removeProjectIds"] == ["project_2"]
    assert sent_json["isCollaborative"] is True


