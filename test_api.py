import os
import requests

API_KEY = "by3QVQRkoNAZR2E9peEUiFC5MyhYTMkASL6qGRv7I5hWZisA7Joomgb7hPjPzk9u"
URL = "https://api.collegefootballdata.com/games"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}
params = {"year": 2024, "seasonType": "regular", "classification": "fbs"}

print(f"Connecting to CFBD API with key ending in ...{API_KEY[-6:]}")
r = requests.get(URL, headers=headers, params=params, timeout=15)

print(f"HTTP Status Code: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"SUCCESS! Retrieved {len(data)} games from 2024.")
    if len(data) > 0:
        sample = data[0]
        print(f"Sample game: {sample.get('home_team')} ({sample.get('home_points')}) vs {sample.get('away_team')} ({sample.get('away_points')})")
else:
    print(f"FAILURE RESPONSE: {r.text}")