import requests
import json
from os.path import expanduser
from urllib.parse import urljoin
from time import sleep

# 1. Authenticate
s = requests.Session()
with open('/Users/tsengch/credential.json', 'r') as f:
    cred_dict = json.load(f)
    s.auth = (cred_dict["email"], cred_dict["password"])
    # print(s.auth)
    resp = s.post('https://api.worldquantbrain.com/authentication')
    if resp.status_code == 401 and resp.headers.get('WWW-Authenticate') == 'persona':
        bio_url = urljoin(resp.url, resp.headers['Location'])
        input(f'Complete biometrics at: {bio_url}\nPress Enter when done...')
        s.post(bio_url)
        print('Authenticated.')
    else:
        print("auth status code: {}".format(resp.status_code))
# 2. Define the alpha
payload = {
    'type': 'REGULAR',
    'settings': {
        'instrumentType': 'EQUITY',
        'region': 'USA',
        'universe': 'TOP3000',
        'delay': 1,
        'decay': 15,
        'neutralization': 'SUBINDUSTRY',
        'truncation': 0.08,
        'pasteurization': 'ON',
        'testPeriod': 'P1Y6M',
        'unitHandling': 'VERIFY',
        'nanHandling': 'OFF',
        'language': 'FASTEXPR',
        'visualization': False,
    },
    'regular': '-returns',
}
# 3. Submit and poll
sim_resp = s.post('https://api.worldquantbrain.com/simulations', json=payload)
location_url = sim_resp.headers['Location']
while True:
    progress = s.get(location_url)
    retry_after = progress.headers.get('Retry-After', 0)
    if retry_after == 0:
        break
    print(f'Waiting {retry_after}s...')
    sleep(float(retry_after))
# 4. Get results
result = progress.json()
with open("test_api_result.json", "w") as f:
    json.dump(result, f)

alpha_id = result['alpha']
result = s.get(f'https://api.worldquantbrain.com/alphas/{alpha_id}').json()
print(f"Sharpe: {result['is']['sharpe']}")
print(f"Fitness: {result['is']['fitness']}")
print(f"Turnover: {result['is']['turnover']}")
