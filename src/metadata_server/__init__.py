import json

def store_metadata(metadata):
	with open('metadata.json', 'w') as f:
		f.write(json.dumps(metadata))

def retrieve_metadata(file_id):
	with open('metadata.json', 'r') as f:
		return json.loads(f.read())
