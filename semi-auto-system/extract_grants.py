import json 
import os
from dotenv import load_dotenv
from google import genai

# load environment variables
load_dotenv()

# load api key
api_key = os.getenv("GEMINI_API_KEY")

# Handle gracefully if API does not exist
if not api_key:
    raise ValueError("No GEMINI AI API key found in the .env file")

# configure gemini
client = genai.Client(api_key=api_key)

# load sources file
SOURCES_FILE = 'semi-auto-system\config\sources_list.json'

with open(SOURCES_FILE, 'r') as f:
    sources = json.load(f).get('sources', [])

print(f'loaded {len(sources)} sources.')
print(f'first source: {sources[0] if sources else None}')


# Test gemini connection
response = client.models.generate_content(
    model="gemini-2.5-flash", contents="Explain how AI works in a few words"
)
print(f"Gemini response: {response.text}")