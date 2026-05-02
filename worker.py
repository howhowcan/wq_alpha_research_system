import os
import time
import pickle
import random
import datetime
from datetime import timedelta
from typing import Dict, List, Tuple

import json
import requests

from alpha import Alpha, AlphaStage, DB_PATH

_SESSION_CACHE = os.path.join(DB_PATH, 'session_cache.pkl')
_CREDENTIAL_FILE = '/Users/tsengch/credential.json'
TIMEOUT = 4  # hours
SIM_LIMIT = 3


class BrainSession:
    def __init__(self):
        self.login()

    def login(self, force_relogin=False):
        if not force_relogin and os.path.exists(_SESSION_CACHE) and self._session_is_valid():
            with open(_SESSION_CACHE, 'rb') as f:
                self._sess = pickle.load(f)
        else:
            self._sess = requests.Session()
            with open(_CREDENTIAL_FILE, 'r') as f:
                cred_dict = json.load(f)
            self._sess.auth = (cred_dict["email"], cred_dict["password"])
            self._sess.post(
                'https://api.worldquantbrain.com/authentication'
            ).raise_for_status()
            with open(_SESSION_CACHE, 'wb') as f:
                pickle.dump(self._sess, f)

    def _session_is_valid(self) -> bool:
        return (datetime.datetime.now() -
                datetime.datetime.fromtimestamp(os.path.getmtime(_SESSION_CACHE))) < timedelta(hours=TIMEOUT)

    def _request(self, method, *args, **kwargs):
        resp = getattr(self._sess, method)(*args, **kwargs)
        if resp.status_code == 401:
            self.login(force_relogin=True)
            resp = getattr(self._sess, method)(*args, **kwargs)
        if resp.status_code in [200, 201]:
            return resp
        raise Exception(f'Request failed: status={resp.status_code}, headers={resp.headers}')

    def get(self, *args, **kwargs):
        return self._request('get', *args, **kwargs)

    def post(self, *args, **kwargs):
        return self._request('post', *args, **kwargs)

    def patch(self, *args, **kwargs):
        return self._request('patch', *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self._request('delete', *args, **kwargs)


class Worker:
    def __init__(self):
        self.sess = BrainSession()

    @staticmethod
    def get_pending_filepaths(running_filepaths: List[str]) -> List[str]:
        pending_dir = AlphaStage.PENDING.value
        if not os.path.exists(pending_dir):
            return []
        result = []
        for fname in os.listdir(pending_dir):
            if fname.endswith('.json') and not fname.startswith('tmp'):
                full_path = os.path.join(pending_dir, fname)
                if full_path not in running_filepaths:
                    result.append(full_path)
        return result

    def _post_payload(self, alpha: Alpha) -> Tuple[bool, str]:
        print("sending alpha: {}".format(json.dumps(alpha.payload)))
        resp = self.sess.post('https://api.worldquantbrain.com/simulations', json=alpha.payload)
        if resp.status_code in [200, 201] and 'Location' in resp.headers:
            return (True, resp.headers['Location'])
        return (False, '')

    def _get_status(self, location_url: str) -> Tuple[bool, str, str]:
        resp = self.sess.get(location_url)
        if resp.status_code not in [200, 201]:
            return (False, '0', '')
        retry_after = resp.headers.get('Retry-After', '0')
        if retry_after == '0':
            data = resp.json()
            if 'alpha' not in data:
                return (False, '0', '')
            return (True, '0', data['alpha'])
        return (True, retry_after, '')

    def _get_result(self, alpha_id: str) -> dict:
        resp = self.sess.get(f'https://api.worldquantbrain.com/alphas/{alpha_id}')
        return resp.json()

    def run(self):
        running_simulations: Dict[str, str] = {}  # filepath -> location_url
        try:
            while True:
                # (1) Fill up to SIM_LIMIT from pending
                pending = self.get_pending_filepaths(list(running_simulations.keys()))
                for fpath in pending:
                    if len(running_simulations) >= SIM_LIMIT:
                        break
                    alpha = Alpha.load(fpath)
                    success, location = self._post_payload(alpha)
                    if success:
                        running_simulations[fpath] = location
                    else:
                        alpha.update_stage(AlphaStage.ERROR)
                    time.sleep(1)

                # (2) Check running simulations
                for fpath, location_url in list(running_simulations.items()):
                    success, retry_after, alpha_id = self._get_status(location_url)
                    if not success:
                        alpha = Alpha.load(fpath)
                        alpha.update_stage(AlphaStage.ERROR)
                        del running_simulations[fpath]
                        break
                    if retry_after == '0' and alpha_id:
                        alpha = Alpha.load(fpath)
                        alpha._json['result'] = self._get_result(alpha_id)
                        alpha.update_stage(AlphaStage.COMPLETE)
                        del running_simulations[fpath]
                        break
                    else:
                        time.sleep(float(retry_after))

                # (3) If nothing running, sleep
                if not running_simulations:
                    time.sleep(5)
        finally:
            for fpath, location_url in running_simulations.items():
                try:
                    self.sess.delete(location_url)
                except Exception:
                    pass


class FakeWorker(Worker):
    """Worker that returns random results without calling the real API."""

    def __init__(self):
        self.sess = requests.Session()

    def _post_payload(self, alpha: Alpha) -> Tuple[bool, str]:
        return (True, 'https://fake.url')

    def _get_status(self, location_url: str) -> Tuple[bool, str, str]:
        return (True, '0', 'fake_id')

    def _get_result(self, alpha_id: str) -> dict:
        return {
            'is': {
                'sharpe': random.uniform(-0.6, 2.4),
                'turnover': random.uniform(0, 1),
                'fitness': 0,
                'returns': 0,
                'drawdown': 0,
                'margin': 0,
            },
            'startDate': '2012-07-15',
        }


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Worker daemon for processing alpha simulations')
    parser.add_argument('--fake', action='store_true', help='Use FakeWorker with random results')
    args = parser.parse_args()

    from alpha import init_db
    init_db()

    if args.fake:
        print('[worker] Starting FakeWorker daemon...')
        worker = FakeWorker()
    else:
        print('[worker] Starting Worker daemon...')
        worker = Worker()

    print(f'[worker] Watching {AlphaStage.PENDING.value} for new alphas')
    print('[worker] Press Ctrl+C to stop')
    try:
        worker.run()
    except KeyboardInterrupt:
        print('\n[worker] Stopped.')
