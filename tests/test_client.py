import pytest
from unittest.mock import patch, Mock

# Assumendo che tu abbia salvato la classe AdriaClient nel file src/client/api.py
from client.api import AdriaClient

# Il decoratore @patch "intercetta" la funzione post della libreria requests.
# mock_post è il nostro "Server finto" che ci viene passato come parametro.
@patch('client.core.requests.Session.post')
def test_client_register_success(mock_post):
    """Tests if the register function sends the correct JSON payload."""
    
    # --- 1. SETUP (Arrange) ---
    # Prepariamo la nostra finta risposta del server (HTTP 201 Created)
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": 1, "username": "mario"}
    mock_response.raise_for_status.return_value = None  # Nessun errore di rete
    
    # Diciamo al nostro finto server di restituire questa risposta
    mock_post.return_value = mock_response

    # --- 2. EXECUTE (Act) ---
    # Istanziamo il nostro client con un URL inventato
    client = AdriaClient("http://fake-server:5000")
    result = client.register("mario", "password123")

    # --- 3. VERIFY (Assert) ---
    # Verifichiamo che il client ci restituisca il dizionario atteso
    assert result["username"] == "mario"
    
    # La parte più importante: verifichiamo che il client abbia provato
    # a inviare i dati giusti, all'URL giusto, formattati come JSON!
    mock_post.assert_called_once_with(
        "http://fake-server:5000/register",
        json={"username": "mario", "password": "password123"}
    )

@patch('client.core.requests.Session.post')
def test_client_login_success(mock_post):
    """Tests if login successfully stores the JWT token in session headers."""
    
    # --- 1. SETUP ---
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"token": "my-secret-jwt-token"}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    # --- 2. EXECUTE ---
    client = AdriaClient("http://fake-server:5000")
    client.login("mario", "password123")

    # --- 3. VERIFY ---
    # Verifichiamo che il token sia stato salvato nella nostra "struct"
    assert client.auth_token == "my-secret-jwt-token"
    # Verifichiamo che la sessione sia pronta a mandare il token nelle chiamate future!
    assert client.session.headers["Authorization"] == "Bearer my-secret-jwt-token"
