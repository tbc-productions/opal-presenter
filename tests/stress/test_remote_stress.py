"""Check the load driver against real HTTP responses without launching a user's app."""

from argparse import ArgumentTypeError
from concurrent.futures import Future
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from types import SimpleNamespace

import pytest

from scripts.stress_remote import Remote, Results, positive, run


@pytest.fixture
def server():
    state = {'id': 'song', 'slide': 1, 'fail': False, 'ignore_commands': False, 'posts': []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            endpoint = self.path.removeprefix('/api/v2/')
            if endpoint == 'core/system':
                payload = {'api_version': 2}
            elif endpoint == 'service/items':
                payload = [{'id': name, 'is_valid': True} for name in ['song', 'presentation', 'video']]
            else:
                payload = {'id': state['id'], 'slides': [
                    {'selected': index == state['slide']} for index in range(3)]}
            self.send_response(500 if state['fail'] else 200)
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            state['posts'].append((self.path, payload))
            if not state['ignore_commands']:
                if self.path.endswith('service/show'):
                    state['id'], state['slide'] = payload['id'], 0
                else:
                    state['slide'] = payload['id']
            self.send_response(204)
            self.end_headers()

    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield Remote(f'http://127.0.0.1:{httpd.server_port}', .1), state
    httpd.shutdown()
    thread.join()
    httpd.server_close()


def args(**overrides):
    return SimpleNamespace(**({'control': False, 'duration': .2, 'clients': 2, 'rate': 40,
                              'max_p95_ms': 1000, 'operator_interval': .02, 'url': 'test'} | overrides))


def test_concurrent_reads_and_report(server):
    remote, state = server
    report = run(args(duration=1), remote)
    assert report['passed']
    assert len(report['operations']) == 4
    assert all(stats['count'] >= 2 for stats in report['operations'].values())
    assert state['posts'] == []


def test_control_checks_service_and_slides_and_restores_original(server):
    remote, state = server
    report = run(args(control=True, duration=.4), remote)
    assert report['passed']
    assert report['operations']['operator/confirmed-slide']['count'] >= 3
    assert {'song', 'presentation', 'video'} <= {
        payload['id'] for path, payload in state['posts'] if path.endswith('service/show')}
    assert (state['id'], state['slide']) == ('song', 1)
    assert report['operations']['operator/restore']['failures'] == 0
    assert any(path.endswith('controller/show') and payload['id'] == 2 for path, payload in state['posts'])


def test_http_failures_fail_the_run(server):
    remote, state = server
    state['fail'] = True
    report = run(args(), remote)
    assert not report['passed']
    assert all(stats['failures'] == stats['count'] for stats in report['operations'].values())
    assert report['recent_errors']


def test_accepted_but_unapplied_command_fails(server):
    remote, state = server
    state['ignore_commands'] = True
    report = run(args(control=True), remote)
    assert not report['passed']
    assert report['operations']['operator/confirmed-slide']['failures'] > 0
    assert any('did not reach' in error['error'] for error in report['recent_errors'])


def test_confirmation_allows_transient_empty_state(monkeypatch):
    remote = Remote('http://localhost', 1)
    responses = iter([{}, {'id': 'song', 'slides': [{'selected': False}]},
                      {'id': 'song', 'slides': [{'selected': True}]}])
    monkeypatch.setattr(remote, 'request', lambda endpoint: next(responses))
    assert remote.wait_for('song', 0)['id'] == 'song'


def test_wrong_response_shape_fails(server, monkeypatch):
    remote, _ = server
    monkeypatch.setattr(remote, 'request', lambda endpoint: 'unexpected')
    report = run(args(), remote)
    assert not report['passed']
    assert all(stats['failures'] > 0 for stats in report['operations'].values())


def test_missing_live_service_prevents_control(server):
    remote, state = server
    state['id'] = 'not-in-service'
    with pytest.raises(ValueError, match='valid service'):
        run(args(control=True), remote)
    assert state['posts'] == []


def test_cancellation_stops_clients_and_restores_output(server, monkeypatch):
    remote, state = server

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(Future, 'result', interrupt)
    report = run(args(control=True, duration=10), remote)
    assert report['cancelled'] and not report['passed']
    assert report['elapsed_seconds'] < 2
    assert (state['id'], state['slide']) == ('song', 1)


def test_latency_budget_and_bounded_samples():
    results = Results()
    for _ in range(10001):
        results.record('read', 0)
    report = results.report(1, 1)
    assert not report['passed']
    assert report['operations']['read']['count'] == 10001
    assert report['operations']['read']['latency_samples'] == 10000


@pytest.mark.parametrize('value', ['0', '-1', 'nan', 'inf'])
def test_invalid_workload_values(value):
    with pytest.raises(ArgumentTypeError):
        positive(value)
