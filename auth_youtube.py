"""One-time YouTube OAuth2 authorization. Run locally, then copy token.json to server."""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=8080)

with open("token.json", "w") as f:
    f.write(creds.to_json())

print("Authorization complete. token.json saved.")
print("Copy token.json to server: scp token.json root@157.180.126.66:/app/")
