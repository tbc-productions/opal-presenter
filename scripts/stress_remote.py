#!/usr/bin/env python3
"""Exercise a running Opal Presenter with paced remote clients and one operator."""

import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import threading
import time
from urllib.request import Request, urlopen


READS = {
    'core/system': dict,
    'service/items': list,
    'controller/live-item': dict,
    'controller/live-items': dict,
}


class Results:
    """Keep counts for the whole run, with bounded latency and error samples."""

    def __init__(self):
        self.lock = threading.Lock()
        self.operations = {}
        self.errors = deque(maxlen=20)

    def record(self, name, started, error=None):
        elapsed = (time.monotonic() - started) * 1000
        with self.lock:
            stats = self.operations.setdefault(name, {
                'count': 0, 'failures': 0, 'max_ms': 0, 'samples': deque(maxlen=10000)})
            stats['count'] += 1
            stats['failures'] += int(error is not None)
            stats['max_ms'] = max(stats['max_ms'], elapsed)
            stats['samples'].append(elapsed)
            if error is not None:
                self.errors.append({'operation': name, 'error': str(error)})

    def report(self, elapsed, budget):
        operations = {}
        for name, stats in self.operations.items():
            samples = sorted(stats['samples'])
            operations[name] = {
                key: value for key, value in stats.items() if key != 'samples'}
            operations[name].update({
                'latency_samples': len(samples),
                'p50_ms': samples[math.ceil(len(samples) * .50) - 1],
                'p95_ms': samples[math.ceil(len(samples) * .95) - 1],
            })
        passed = bool(operations) and all(
            stats['failures'] == 0 and stats['p95_ms'] <= budget for stats in operations.values())
        return {'passed': passed, 'elapsed_seconds': elapsed, 'p95_budget_ms': budget,
                'operations': operations, 'recent_errors': list(self.errors)}


class Remote:
    def __init__(self, url, timeout, token=''):
        self.url = url.rstrip('/') + '/api/v2/'
        self.timeout = timeout
        self.token = token

    def request(self, endpoint, data=None):
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = self.token
        request = Request(self.url + endpoint,
                          data=json.dumps(data).encode() if data is not None else None, headers=headers)
        with urlopen(request, timeout=self.timeout) as response:
            expected_status = 204 if data is not None and endpoint != 'core/login' else 200
            if response.status != expected_status:
                raise ValueError(f'{endpoint}: expected HTTP {expected_status}, got {response.status}')
            body = response.read()
        return json.loads(body) if body else None

    def live(self):
        item = self.request('controller/live-items')
        if not isinstance(item, dict) or not isinstance(item.get('slides'), list) or not item['slides']:
            raise ValueError('Load a service and send an item live before using --control')
        selected = [index for index, slide in enumerate(item['slides']) if slide.get('selected')]
        if len(selected) != 1 or not item.get('id'):
            raise ValueError('The live item must have exactly one selected slide and an id')
        return item, selected[0]

    def wait_for(self, item_id, slide=None):
        deadline = time.monotonic() + self.timeout
        while True:
            item = self.request('controller/live-items')
            if not isinstance(item, dict):
                raise ValueError('Unexpected live-item response shape')
            slides = item.get('slides', [])
            selected = [index for index, page in enumerate(slides) if page.get('selected')]
            if item.get('id') == item_id and len(selected) == 1 and (slide is None or selected == [slide]):
                return item
            if time.monotonic() >= deadline:
                raise TimeoutError('Accepted remote command did not reach the live controller')
            time.sleep(.05)


def run(args, remote):
    results = Results()
    original = remote.live() if args.control else None
    items = remote.request('service/items') if args.control else []
    items = [item for item in items if item.get('is_valid')]
    if args.control and (not items or original[0]['id'] not in [item['id'] for item in items]):
        raise ValueError('--control requires a valid service containing the current live item')
    started = time.monotonic()
    deadline = started + args.duration
    stop = threading.Event()
    cancelled = False

    def readers():
        index = 0
        endpoints = list(READS)
        while not stop.is_set() and time.monotonic() < deadline:
            tick = time.monotonic()
            endpoint = endpoints[index % len(endpoints)]
            try:
                payload = remote.request(endpoint)
                if not isinstance(payload, READS[endpoint]):
                    raise ValueError('Unexpected JSON response shape')
                if endpoint == 'core/system' and payload.get('api_version') != 2:
                    raise ValueError('Expected API version 2')
            except Exception as error:
                results.record(endpoint, tick, error)
            else:
                results.record(endpoint, tick)
            index += 1
            stop.wait(max(0, min(deadline - time.monotonic(), 1 / args.rate - (time.monotonic() - tick))))

    def operator():
        index = 0
        try:
            while not stop.is_set() and time.monotonic() < deadline:
                tick = time.monotonic()
                try:
                    item_id = items[index % len(items)]['id']
                    remote.request('service/show', {'id': item_id})
                    live = remote.wait_for(item_id)
                    # Exercise first/last pages, including native presentation slide commands.
                    for slide in dict.fromkeys([0, len(live['slides']) - 1]):
                        remote.request('controller/show', {'id': slide})
                        remote.wait_for(item_id, slide)
                except Exception as error:
                    results.record('operator/confirmed-slide', tick, error)
                else:
                    results.record('operator/confirmed-slide', tick)
                index += 1
                stop.wait(max(0, min(deadline - time.monotonic(),
                                     args.operator_interval - (time.monotonic() - tick))))
        finally:
            tick = time.monotonic()
            try:
                remote.request('service/show', {'id': original[0]['id']})
                remote.wait_for(original[0]['id'])
                remote.request('controller/show', {'id': original[1]})
                remote.wait_for(original[0]['id'], original[1])
            except Exception as error:
                results.record('operator/restore', tick, error)
            else:
                results.record('operator/restore', tick)

    with ThreadPoolExecutor(max_workers=args.clients + int(args.control)) as pool:
        futures = [pool.submit(readers) for _ in range(args.clients)]
        if args.control:
            futures.append(pool.submit(operator))
        try:
            for future in futures:
                future.result()
        except KeyboardInterrupt:
            cancelled = True
            stop.set()
    report = results.report(time.monotonic() - started, args.max_p95_ms)
    if cancelled:
        report.update(passed=False, cancelled=True)
    report['workload'] = {'url': args.url, 'clients': args.clients, 'requests_per_second_per_client': args.rate,
                          'control': args.control, 'duration_seconds': args.duration}
    return report


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('must be finite and greater than zero')
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:4316')
    parser.add_argument('--duration', type=positive, default=60, help='seconds')
    parser.add_argument('--clients', type=int, default=8)
    parser.add_argument('--rate', type=positive, default=2, help='requests/second/client')
    parser.add_argument('--timeout', type=positive, default=5, help='request and command timeout in seconds')
    parser.add_argument('--max-p95-ms', type=positive, default=1000)
    parser.add_argument('--operator-interval', type=positive, default=2, help='seconds between service changes')
    parser.add_argument('--control', action='store_true', help='changes live output; use a rehearsal service')
    parser.add_argument('--report', type=Path, default=Path('output/stress-remote.json'))
    args = parser.parse_args()
    if args.clients < 1:
        parser.error('--clients must be at least 1')
    remote = Remote(args.url, args.timeout, os.environ.get('OPAL_STRESS_TOKEN', ''))
    try:
        if os.environ.get('OPAL_STRESS_PASSWORD'):
            remote.token = remote.request('core/login', {
                'username': os.environ.get('OPAL_STRESS_USERNAME', ''),
                'password': os.environ['OPAL_STRESS_PASSWORD']})['token']
        report = run(args, remote)
    except Exception as error:
        report = {'passed': False, 'error': str(error)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
