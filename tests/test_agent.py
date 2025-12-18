import pytest
from unittest.mock import patch, MagicMock
from tools.agent import list_agents, get_agent, delete_agent, list_agent_categories, list_agent_tools

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

