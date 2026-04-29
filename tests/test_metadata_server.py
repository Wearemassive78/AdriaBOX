import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
# add src/ to sys.path so `metadata_server` package can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from metadata_server import store_metadata, retrieve_metadata


class TestMetadataServer(unittest.TestCase):
    
    @patch('builtins.open', new_callable=mock_open)
    def test_store_metadata(self, mock_file):
        metadata = {'file_id': '123', 'chunks': 1}
        store_metadata(metadata)
        
        mock_file.assert_called_once_with('metadata.json', 'w')
        handle = mock_file()
        handle.write.assert_called_once_with('{"file_id": "123", "chunks": 1}')
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"file_id": "123", "chunks": 1}')
    def test_retrieve_metadata(self, mock_file):
        result = retrieve_metadata('123')
        
        mock_file.assert_called_once_with('metadata.json', 'r')
        self.assertEqual(result['file_id'], '123')
        self.assertEqual(result['chunks'], 1)


if __name__ == '__main__':
    unittest.main()