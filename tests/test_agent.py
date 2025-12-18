import pytest
from unittest.mock import patch, MagicMock
from tools.agent import create_agent, list_agents, get_agent, delete_agent, list_agent_categories, list_agent_tools

@pytest.fixture
def mock_resp():
    mock = MagicMock()
    mock.status_code = 200
    mock.headers = {"content-type": "application/json"}
    mock.json.return_value = {"success": True}
    return mock

@patch("tools.agent.resilient_request")
@patch("tools.agent.default_headers")
def test_list_agents(mock_headers, mock_request, mock_resp):
    mock_headers.return_value = {"Authorization": "Bearer test"}
    mock_request.return_value = mock_resp
    
    result = list_agents(page=1, limit=10)
    
    assert result == {"success": True}
    mock_request.assert_called_once()

@patch("tools.agent.resilient_request")
@patch("tools.agent.default_headers")
def test_get_agent(mock_headers, mock_request, mock_resp):
    mock_headers.return_value = {"Authorization": "Bearer test"}
    mock_request.return_value = mock_resp
    
    result = get_agent("agent_123")
    
    assert result == {"success": True}
    mock_request.assert_called_once()

@patch("tools.agent.resilient_request")
@patch("tools.agent.default_headers")
def test_delete_agent(mock_headers, mock_request, mock_resp):
    mock_headers.return_value = {"Authorization": "Bearer test"}
    mock_request.return_value = mock_resp
    
    result = delete_agent("agent_123")
    
    assert result == {"success": True}
    mock_request.assert_called_once()

@patch("tools.agent.resilient_request")
@patch("tools.agent.default_headers")
def test_list_agent_categories(mock_headers, mock_request, mock_resp):
    mock_headers.return_value = {"Authorization": "Bearer test"}
    mock_request.return_value = mock_resp
    mock_resp.json.return_value = ["cat1", "cat2"]
    
    result = list_agent_categories()
    
    assert result == ["cat1", "cat2"]
    mock_request.assert_called_once()

@patch("tools.agent.resilient_request")
@patch("tools.agent.default_headers")
def test_list_agent_tools(mock_headers, mock_request, mock_resp):
    mock_headers.return_value = {"Authorization": "Bearer test"}
    mock_request.return_value = mock_resp
    mock_resp.json.return_value = ["tool1", "tool2"]
    
    result = list_agent_tools()
    
    assert result == ["tool1", "tool2"]
    mock_request.assert_called_once()

@patch("tools.agent.resilient_request")
@patch("tools.agent.default_headers")
def test_create_agent_with_project_params(mock_headers, mock_request, mock_resp):
    mock_headers.return_value = {"Authorization": "Bearer test"}
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"id": "agent_123"}
    mock_request.return_value = mock_resp
    
    result = create_agent(
        name="Test Agent",
        provider="openai",
        model="gpt-4",
        projectIds=["p1"],
        removeProjectIds=["p2"],
        isCollaborative=True
    )
    
    assert result == {"id": "agent_123"}
    args, kwargs = mock_request.call_args
    sent_json = kwargs["json"]
    assert sent_json["projectIds"] == ["p1"]
    assert sent_json["removeProjectIds"] == ["p2"]
    assert sent_json["isCollaborative"] is True

