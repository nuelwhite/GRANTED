import json 
import os
from dotenv import load_dotenv


load_dotenv('.env')

SOURCES_FILE = 'semi-auto-system\config\sources_list.json'

with open(SOURCES_FILE, 'r') as f:
    sources = json.load(f).get('sources', [])

print(f'loaded {len(sources)} sources.')
print(f'first source: {sources[0] if sources else None}')