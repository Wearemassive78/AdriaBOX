import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'client'))
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '..'))
from client import send_file_to_node, register_metadata



class TestClient(unittest.TestCase):
    
    @patch('socket.socket')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test data')
    def test_send_file_to_node(self, mock_file, mock_socket):
        mock_sock_instance = MagicMock()
        mock_socket.return_value = mock_sock_instance
        
        send_file_to_node('localhost', 7001, 'testfile.txt')
        
        mock_sock_instance.connect.assert_called_once_with(('localhost', 7001))
        mock_sock_instance.sendall.assert_called()
        mock_sock_instance.close.assert_called_once()
    
    @patch('requests.post')
    def test_register_metadata(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {'file_id': '123', 'chunks': 1}
        mock_post.return_value = mock_response
        
        result = register_metadata('http://localhost:5000', 'testfile.txt', chunks=1)
        
        mock_post.assert_called_once_with(
            'http://localhost:5000/store',
            json={'filename': 'testfile.txt', 'chunks': 1}
        )
        self.assertEqual(result['file_id'], '123')
    
    @patch('requests.post')
    def test_register_metadata_http_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception('HTTP Error')
        mock_post.return_value = mock_response
        
        with self.assertRaises(Exception):
            register_metadata('http://localhost:5000', 'testfile.txt')


if __name__ == '__main__':
    unittest.main()