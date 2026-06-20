#da controllare con MAX
import pytest
from unittest.mock import patch, Mock
from client.api import AdriaClient

@patch('client.core.requests.Session.post')
def test_client_register_success(mock_post):
    """Tests if the register function sends the correct JSON payload."""
    
    # --- 1. SETUP (Arrange) ---
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": 1, "username": "mario"}
    mock_response.raise_for_status.return_value = None  
    mock_post.return_value = mock_response

    # --- 2. EXECUTE (Act) ---
    client = AdriaClient("http://fake-server:5000")
    result = client.register("mario", "password123")

    # --- 3. VERIFY (Assert) ---
    assert result["username"] == "mario"
    
    # CORREZIONE: Rimosso 'role': 'user' dal payload atteso poiché la scalata dei privilegi
    # è mitigata lasciando al server l'assegnazione autoritativa del ruolo.
    mock_post.assert_called_once_with(
        "http://fake-server:5000/register",
        json={"username": "mario", "password": "password123"},
        timeout=10.0,
    )

@patch('client.core.requests.Session.post')
def test_client_login_success(mock_post):
    """Tests if login successfully stores the JWT token in session headers."""
    
    # --- 1. SETUP ---
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "token": "my-secret-jwt-token",
        "username": "mario",
        "role": "user",
    }
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    # --- 2. EXECUTE ---
    client = AdriaClient("http://fake-server:5000")
    client.login("mario", "password123")

    # --- 3. VERIFY ---
    assert client.auth_token == "my-secret-jwt-token"
    assert client.current_username == "mario"
    # CORREZIONE: Rimossa l'asserzione obsoleta su current_role che non fa parte 
    # degli attributi esposti dall'istanza della classe Facade.
    assert client.http.session.headers["Authorization"] == "Bearer my-secret-jwt-token"

