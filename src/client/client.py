import argparse
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import requests
import socket
from common.tcp import send_file
from common.constants import DEFAULT_METADATA_URL, DEFAULT_NODE_HOST, DEFAULT_NODE_TCP_PORT
def send_file_to_node(host, port, filename):
    return send_file(host, port, filename)

def register_metadata(metadata_url, filename, chunks=1):
    r = requests.post(f"{metadata_url}/store", json={'filename': filename, 'chunks': chunks})
    r.raise_for_status()
    return r.json()

def upload_file_to_metadata(metadata_url, filepath):
    """Uploads the actual file to the metadata server's /upload endpoint."""
    with open(filepath, 'rb') as fh:
        files = {'file': (os.path.basename(filepath), fh)}
        r = requests.post(f"{metadata_url}/upload", files=files)
    r.raise_for_status()
    return r.json()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--file')
    parser.add_argument('--metadata', default=DEFAULT_METADATA_URL)
    parser.add_argument('--node-host', default=DEFAULT_NODE_HOST)
    parser.add_argument('--node-tcp-port', type=int, default=DEFAULT_NODE_TCP_PORT)
    parser.add_argument('--interactive', action='store_true', help='Start interactive welcome menu')
    args = parser.parse_args()

    def print_welcome():
        print('Welcome to AdriaBOX client')
        print('Commands:')
        print('  upload <path>    - Upload file to metadata server and register it')
        print('  register <name>  - Register metadata only (no file upload)')
        print('  send <path>      - Send file to storage node via TCP')
        print('  list             - List files registered in metadata server')
        print('  help             - Show this help')
        print('  exit             - Exit the interactive prompt')

    def list_metadata(metadata_url):
        try:
            r = requests.get(f"{metadata_url}/files")
            r.raise_for_status()
            files = r.json()
            if not files:
                print('No files registered')
                return
            for f in files:
                print(f"{f.get('id')}: {f.get('filename')} (chunks={f.get('chunks')})")
        except Exception as e:
            print('Failed to list files:', e)

    def interactive_loop():
        print_welcome()
        while True:
            try:
                cmd = input('adria> ').strip()
            except (EOFError, KeyboardInterrupt):
                print('\nExiting')
                break
            if not cmd:
                continue
            parts = cmd.split(maxsplit=1)
            action = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else None

            if action == 'upload':
                if not arg:
                    print('Usage: upload <path>')
                    continue
                try:
                    info = upload_file_to_metadata(args.metadata, arg)
                    print('Uploaded:', info)
                except Exception as e:
                    print('Upload failed:', e)
            elif action == 'register':
                if not arg:
                    print('Usage: register <filename>')
                    continue
                try:
                    info = register_metadata(args.metadata, os.path.basename(arg), chunks=1)
                    print('Registered metadata:', info)
                except Exception as e:
                    print('Register failed:', e)
            elif action == 'send':
                if not arg:
                    print('Usage: send <path>')
                    continue
                try:
                    send_file_to_node(args.node_host, args.node_tcp_port, arg)
                    print('File sent to storage node')
                except Exception as e:
                    print('Send failed:', e)
            elif action == 'list':
                list_metadata(args.metadata)
            elif action == 'help':
                print_welcome()
            elif action == 'exit':
                break
            else:
                print('Unknown command. Type "help" for commands.')

    # If interactive flag is set or no file provided, start interactive menu
    if args.interactive or not args.file:
        interactive_loop()
    else:
        # Non-interactive single operation: upload then send
        try:
            info = upload_file_to_metadata(args.metadata, args.file)
            print('Metadata server saved file:', info)
        except Exception as e:
            print('Warning: failed to upload to metadata server:', e)
        send_file_to_node(args.node_host, args.node_tcp_port, args.file)
        print('File sent to storage node')
