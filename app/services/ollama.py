"""Only the loopback Ollama server; no proxies, remote endpoints or cloud tags."""
import http.client
import json


def local_tag(tag):
    if not tag or any(x in tag.lower() for x in ['cloud', '/', '\\', 'http', '@']) or ':' not in tag:
        raise ValueError('Choose an explicit local Ollama tag, such as llama3.2:3b.')
    return tag


class Ollama:
    def _request(self, path, body=None, job=None, connection=None):
        conn = connection or http.client.HTTPConnection('127.0.0.1', 11434, timeout=2 if body is None else 600)
        try:
            conn.request('GET' if body is None else 'POST', path,
                body=None if body is None else json.dumps(body), headers={'Content-Type': 'application/json'})
            response = conn.getresponse()
            conn._clipify_response = response
            if response.status != 200:
                raise RuntimeError(f'Ollama returned {response.status}: {response.read(300).decode(errors="replace")}')
            if body is None or not body.get('stream'):
                return json.loads(response.read())
            result = ''
            # Streaming tokens provides cooperative cancellation between responses.
            while True:
                if job:
                    job.check()
                line = response.readline()
                if not line:
                    break
                item = json.loads(line)
                if 'error' in item:
                    raise RuntimeError(item['error'])
                result += item.get('response', '')
                if item.get('done'):
                    return result
            raise RuntimeError('Ollama disconnected before finishing. This window can be resumed.')
        except OSError as e:
            raise RuntimeError('Local Ollama is unavailable or timed out. Start Ollama and check its local models.') from e
        finally:
            conn.close()

    def request(self, path, body=None, job=None):
        if job is None:
            return self._request(path, body)
        import threading
        import queue
        import socket
        conn = http.client.HTTPConnection('127.0.0.1', 11434, timeout=600)
        result = queue.Queue()
        def work():
            try:
                result.put((True, self._request(path, body, job, conn)))
            except Exception as e:
                result.put((False, e))
        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        try:
            while True:
                job.check()
                try:
                    ok, value = result.get(timeout=.15)
                except queue.Empty:
                    continue
                if ok:
                    return value
                raise value
        finally:
            response = getattr(conn, '_clipify_response', None)
            raw = getattr(getattr(response, 'fp', None), 'raw', None)
            sock = conn.sock or getattr(raw, '_sock', None)
            if sock:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            conn.close()

    def models(self):
        return [m['name'] for m in self.request('/api/tags').get('models', [])]

    def require(self, tag):
        local_tag(tag)
        entries = self.request('/api/tags').get('models', [])
        found = next((m for m in entries if m.get('name') == tag), None)
        if found is None:
            raise RuntimeError(f'Local model {tag} is missing. No model was downloaded automatically.')
        if found.get('remote_model') or found.get('remote_host'):
            raise RuntimeError('This model points to remote inference. Choose a fully local model.')

    def generate(self, tag, prompt, job, images=None):
        local_tag(tag)
        body = {'model': tag, 'prompt': prompt, 'stream': True, 'format': 'json',
            'keep_alive': 0, 'options': {'temperature': .2, 'num_ctx': 8192, 'num_predict': 2000}}
        if images:
            body['images'] = images
        result = self.request('/api/generate', body, job)
        return json.loads(result)
