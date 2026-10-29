"""Small stdlib HTTPS client for the companion wire protocol."""
import hashlib
import http.client
import json
import os
import ssl
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import quote, urlencode


ProgressCallback = Callable[[int, int], None]


class PinnedHttpsClient:
    CHUNK_SIZE = 64 * 1024

    def __init__(
        self,
        host: str,
        port: int,
        fingerprint: str | None,
        token: str | None = None,
    ) -> None:
        self.host, self.port = host, int(port)
        self.fingerprint = fingerprint.lower() if fingerprint else None
        self.token = token
        self.observed_fingerprint = None

    def _connect(self, timeout: float | None = None) -> http.client.HTTPSConnection:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        connection = http.client.HTTPSConnection(
            self.host, self.port, context=context, timeout=timeout
        )
        connection.connect()
        certificate = connection.sock.getpeercert(binary_form=True)
        observed = hashlib.sha256(certificate).hexdigest()
        self.observed_fingerprint = observed
        if self.fingerprint and observed.lower() != self.fingerprint:
            connection.close()
            raise PermissionError(
                'Media File Explorer certificate fingerprint mismatch'
            )
        return connection

    @staticmethod
    def _raise_response_error(response: http.client.HTTPResponse) -> None:
        raw = response.read()
        try:
            message = (
                json.loads(raw.decode('utf-8')).get('message')
                or raw.decode('utf-8')
            )
        except (ValueError, AttributeError):
            message = raw.decode('utf-8', errors='replace') or response.reason
        error = {
            404: FileNotFoundError,
            409: FileExistsError,
            401: PermissionError,
            403: PermissionError,
        }.get(response.status, OSError)
        raise error(message)

    def _request(
        self,
        method: str,
        route: str,
        params: Mapping[str, str | int] | None = None,
        body: Any = None,
        timeout: float | None = None,
        stream: bool = False,
    ) -> Any:
        path = route
        if params:
            path += ('&' if '?' in path else '?') + urlencode(
                params, doseq=True, quote_via=quote
            )
        connection = self._connect(timeout)
        headers = (
            {'Authorization': 'Bearer ' + self.token} if self.token else {}
        )
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            if response.status >= 400:
                self._raise_response_error(response)
            if stream:
                return connection, response
            raw = response.read()
            return json.loads(raw.decode('utf-8')) if raw else {}
        except Exception:
            connection.close()
            raise

    def get_json(
        self, route: str, params: Mapping[str, str | int] | None = None
    ) -> Any:
        return self._request('GET', route, params=params)

    def post_json(
        self, route: str, body: Mapping[str, Any], timeout: float | None = None
    ) -> tuple[Any, str | None]:
        result = self._request('POST', route, body=body, timeout=timeout)
        return result, self.observed_fingerprint
    def delete(
        self, route: str, params: Mapping[str, str | int] | None = None
    ) -> Any:
        return self._request('DELETE', route, params=params)

    def download(
        self,
        api_path: str,
        local_path: str,
        progress_cb: ProgressCallback | None = None,
    ) -> None:
        connection, response = self._request(
            'GET', '/v1/file', {'path': api_path}, stream=True
        )
        total, received = int(response.getheader('Content-Length') or -1), 0
        try:
            with open(local_path, 'wb') as output:
                while True:
                    chunk = response.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    output.write(chunk)
                    received += len(chunk)
                    if progress_cb:
                        progress_cb(received, total)
        finally:
            response.close()
            connection.close()

    def upload(
        self,
        local_path: str,
        api_path: str,
        progress_cb: ProgressCallback | None = None,
    ) -> None:
        length = os.path.getsize(local_path)
        path = '/v1/file?' + urlencode({'path': api_path}, quote_via=quote)
        connection = self._connect()
        try:
            connection.putrequest('PUT', path)
            connection.putheader('Content-Length', str(length))
            if self.token:
                connection.putheader('Authorization', 'Bearer ' + self.token)
            connection.endheaders()
            sent = 0
            with open(local_path, 'rb') as source:
                while True:
                    chunk = source.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    connection.send(chunk)
                    sent += len(chunk)
                    if progress_cb:
                        progress_cb(sent, length)
            response = connection.getresponse()
            if response.status >= 400:
                self._raise_response_error(response)
            response.read()
        finally:
            connection.close()
