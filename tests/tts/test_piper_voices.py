import hashlib
import json
from pathlib import Path
import pytest
import src.tts.piper_voices as piper_voices
from src.tts.piper_voices import PiperVoiceStore

BASE_URL = 'https://example.invalid/voices'


class FakeResponse:
    def __init__(self, content: bytes, status: int = 200):
        self.content, self.status = content, status
    def raise_for_status(self):
        if self.status != 200:
            raise IOError(f'HTTP {self.status}')
    def json(self):
        return json.loads(self.content)
    def iter_content(self, chunk_size=1):
        yield self.content
    def __enter__(self): return self
    def __exit__(self, *args): return False


@pytest.fixture
def server(monkeypatch):
    """A fake download server: a dict of file name -> content, with the requests made to it"""
    files = {'malenord.onnx': b'nord model', 'malenord.onnx.json': b'{}', 'femalenord.onnx': b'female model', 'femalenord.onnx.json': b'{}'}
    state = {'files': dict(files), 'requests': [], 'online': True}
    manifest = {'format': 1, 'files': {name: {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for name, data in files.items()}}
    state['files']['manifest.json'] = json.dumps(manifest).encode()

    def fake_get(url, **kwargs):
        name = url.rsplit('/', 1)[-1]
        state['requests'].append(name)
        if not state['online']:
            raise IOError('no connection')
        return FakeResponse(state['files'][name]) if name in state['files'] else FakeResponse(b'', 404)
    monkeypatch.setattr(piper_voices.requests, 'get', fake_get)
    return state


def test_voice_is_downloaded_when_needed(tmp_path: Path, server):
    store = PiperVoiceStore(tmp_path / 'bundled', tmp_path / 'downloads', BASE_URL)
    assert store.get_available_voices() == ['femalenord', 'malenord']
    assert store.get_missing_voices() == ['femalenord', 'malenord']

    model = store.get_model_path('malenord')
    assert model == tmp_path / 'downloads' / 'malenord.onnx'
    assert model.read_bytes() == b'nord model'
    assert (tmp_path / 'downloads' / 'malenord.onnx.json').exists()
    assert store.get_missing_voices() == ['femalenord']

    # already on this machine: not downloaded again
    server['requests'].clear()
    assert store.get_model_path('malenord') == model
    assert server['requests'] == []
    assert store.get_model_path('unknownvoice') is None


def test_bundled_voices_are_used_without_downloading(tmp_path: Path, server):
    bundled = tmp_path / 'bundled'
    bundled.mkdir()
    (bundled / 'malenord.onnx').write_bytes(b'bundled model')
    (bundled / 'malenord.onnx.json').write_bytes(b'{}')
    store = PiperVoiceStore(bundled, tmp_path / 'downloads', BASE_URL)
    server['requests'].clear()

    assert store.get_model_path('malenord') == bundled / 'malenord.onnx'
    assert server['requests'] == []


def test_damaged_download_is_discarded(tmp_path: Path, server):
    store = PiperVoiceStore(tmp_path / 'bundled', tmp_path / 'downloads', BASE_URL)
    server['files']['malenord.onnx'] = b'cut off' # does not match the manifest

    assert store.get_model_path('malenord') is None
    assert not (tmp_path / 'downloads' / 'malenord.onnx').exists()
    assert not (tmp_path / 'downloads' / 'malenord.onnx.part').exists()


def test_without_connection_or_with_downloads_disabled(tmp_path: Path, server):
    # downloads disabled: only what is on this machine is offered
    store = PiperVoiceStore(tmp_path / 'bundled', tmp_path / 'downloads', None)
    assert store.get_available_voices() == [] and not store.can_download
    assert server['requests'] == []

    # the list of voices is remembered from an earlier run for when there is no connection
    PiperVoiceStore(tmp_path / 'bundled', tmp_path / 'downloads', BASE_URL)
    server['online'] = False
    offline_store = PiperVoiceStore(tmp_path / 'bundled', tmp_path / 'downloads', BASE_URL)
    assert offline_store.get_available_voices() == ['femalenord', 'malenord']
    assert offline_store.get_model_path('malenord') is None # cannot be downloaded right now


def test_all_missing_voices_are_downloaded_in_background(tmp_path: Path, server):
    store = PiperVoiceStore(tmp_path / 'bundled', tmp_path / 'downloads', BASE_URL)
    store.download_missing_in_background()
    store._PiperVoiceStore__background_thread.join(timeout=10)
    assert store.get_missing_voices() == []
