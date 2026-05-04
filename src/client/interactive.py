import requests
import os

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

def run_interactive(upload_fn, register_fn, send_fn, metadata_url, node_host, node_port):
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
                info = upload_fn(metadata_url, arg)
                print('Uploaded:', info)
            except Exception as e:
                print('Upload failed:', e)
        elif action == 'register':
            if not arg:
                print('Usage: register <filename>')
                continue
            try:
                info = register_fn(metadata_url, os.path.basename(arg), chunks=1)
                print('Registered metadata:', info)
            except Exception as e:
                print('Register failed:', e)
        elif action == 'send':
            if not arg:
                print('Usage: send <path>')
                continue
            try:
                send_fn(node_host, node_port, arg)
                print('File sent to storage node')
            except Exception as e:
                print('Send failed:', e)
        elif action == 'list':
            list_metadata(metadata_url)
        elif action == 'help':
            print_welcome()
        elif action == 'exit':
            break
        else:
            print('Unknown command. Type "help" for commands.')
