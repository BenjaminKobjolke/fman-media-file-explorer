"""Connection and approval state for the local desktop companion."""
from dataclasses import dataclass
import http.client
import time
import uuid

from fman import load_json, save_json
from .companion_http import PinnedHttpsClient

@dataclass(frozen=True)
class Phone:
    device_id: str
    name: str
    host: str
    port: int
    token: str
    fingerprint: str

class CompanionLink:
    SETTINGS_NAME = 'Media File Explorer Settings.json'
    def __init__(self):
        self.settings = load_json(self.SETTINGS_NAME, default={})
        initial = {'port': 47610, 'client_id': str(uuid.uuid4()), 'client_token': None, 'companion_fingerprint': None}
        changed = False
        for key, value in initial.items():
            if key not in self.settings:
                self.settings[key] = value
                changed = True
        if changed:
            self._save()
        self._cached_peers = None
        self._cache_time = 0

    def _save(self):
        save_json(self.SETTINGS_NAME, self.settings)

    def _request_approval(self):
        client = PinnedHttpsClient('127.0.0.1', self.settings['port'], self.settings.get('companion_fingerprint'))
        try:
            result, fingerprint = client.post_json('/v1/client', {'clientId': self.settings['client_id'], 'name': 'fman'}, timeout=130)
        except PermissionError:
            raise
        except (OSError, TimeoutError, ConnectionError, http.client.HTTPException) as error:
            raise OSError('Media File Explorer companion is not running') from error
        return result['token'], fingerprint

    def _ensure_approved(self):
        if self.settings.get('client_token'):
            return
        token, fingerprint = self._request_approval()
        self.settings['client_token'] = token
        self.settings['companion_fingerprint'] = fingerprint
        self._save()

    def _fetch_peers(self):
        self._ensure_approved()
        client = PinnedHttpsClient('127.0.0.1', self.settings['port'], self.settings.get('companion_fingerprint'), self.settings.get('client_token'))
        try:
            result = client.get_json('/v1/peers')
        except PermissionError:
            self.settings['client_token'] = None
            self._save()
            self._ensure_approved()
            client = PinnedHttpsClient('127.0.0.1', self.settings['port'], self.settings.get('companion_fingerprint'), self.settings.get('client_token'))
            try:
                result = client.get_json('/v1/peers')
            except PermissionError:
                raise
            except (OSError, TimeoutError, ConnectionError, http.client.HTTPException) as error:
                raise OSError('Media File Explorer companion is not running') from error
        except (OSError, TimeoutError, ConnectionError, http.client.HTTPException) as error:
            raise OSError('Media File Explorer companion is not running') from error
        return [Phone(p['deviceId'], p['name'], p['host'], int(p['port']), p['token'], p['fingerprint']) for p in result.get('peers', [])]

    def peers(self):
        now = time.monotonic()
        if self._cached_peers is None or now - self._cache_time >= 5:
            self._cached_peers = self._fetch_peers()
            self._cache_time = now
        return list(self._cached_peers)
