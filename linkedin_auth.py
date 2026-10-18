import os
import webbrowser
import urllib.parse
import requests
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8080/")
TOKEN_FILE = Path("data/social/linkedin_token.json")
TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

auth_code = None

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        if 'code' in params:
            auth_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"<h2>Authentication Successful! You can close this window and return to PowerShell.</h2>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Error: No code received.")

def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Missing LinkedIn credentials in .env")
        return

    # Build authorization URL
    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization?"
        f"response_type=code&client_id={CLIENT_ID}&"
        f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}&"
        "scope=w_member_social%20openid%20profile%20email"
    )

    print("Opening browser for LinkedIn authorization...")
    print("If it doesn't open automatically, click this link:")
    print(auth_url)
    webbrowser.open(auth_url)

    # Start local server to catch the callback
    server = HTTPServer(('localhost', 8080), CallbackHandler)
    print("\nWaiting for authorization... (Check your browser)")
    server.handle_request()

    if auth_code:
        print("\nAuthorization code received! Exchanging for access token...")
        token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        payload = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': REDIRECT_URI,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }
        r = requests.post(token_url, data=payload)
        if r.status_code == 200:
            token_data = r.json()
            TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
            print(f"✅ Success! Access Token saved to {TOKEN_FILE}")
            print("You can now post to LinkedIn automatically.")
        else:
            print(f"❌ Failed to get token: {r.text}")

if __name__ == "__main__":
    main()