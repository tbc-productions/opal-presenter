Tests for Opal Presenter
=======================

This directory contains unit tests for Opal Presenter.

Prerequisites
-------------

In order to run the unit tests, you will need the following Python packages/libraries installed:

 - pytest
 - pytestqt
 - flake8

On Ubuntu you can simple install the python3-pytest and flake8 packages.
Most other distributions will also have these packages.
On Windows and Mac OS X you will need to use ``pip`` to install these packages.

Running the Tests
-----------------

To run the tests, navigate to the root directory of the Opal Presenter project, and then run the following command::

    pytest -v tests

JavaScript Tests
----------------

The display tests use Jasmine 7 with jasmine-browser-runner. Install Node.js
22 or 24, pnpm and Google Chrome, then run from the project root::

    pnpm install --frozen-lockfile
    pnpm test

The runner starts a local server and runs the specs in headless Chrome.
Selenium manages the matching ChromeDriver. For interactive debugging, run::

    pnpm test:serve

Open the URL printed by the runner in a browser. The configuration in
``jasmine-browser.mjs`` also serves the image and stylesheet fixtures used by
the iframe rendering tests. Specs retain their existing execution order because
the legacy unit tests share one Display singleton.

Production stress tests
-----------------------

The stress tests are opt-in and use the existing Python and browser test
dependencies. They complement the regression suite; a passing run covers the
workload and machine tested, rather than guaranteeing every glitch is absent.

Display workload
~~~~~~~~~~~~~~~~

Run repeated songs, images, PDF-style image slides and actual MP4 playback::

    pnpm test:stress

If pnpm tries to reinstall an already working dependency tree, invoke the
installed runner directly::

    node node_modules/jasmine-browser-runner/bin/jasmine-browser-runner runSpecs --config=jasmine-stress.mjs

The default run replaces 100 items, with 30 slides per non-video item. It uses
the real Display and Reveal code in headless Chrome, checks selected content,
footers, image backgrounds, decoded video progress, pause/stop, blank/show,
resizing and transition cleanup. Browser errors, unexpected DOM growth or a
95th-percentile deck-render latency above 500 ms fail the run. The render
measurement ends after image readiness and two animation frames; it excludes
the remaining transition duration and video playback checks. Python web-channel
callbacks are substituted, so this does not exercise Qt or native presentations.

Change the workload and latency budget, for example::

    STRESS_CYCLES=1000 STRESS_SLIDES=120 STRESS_P95_MS=500 pnpm test:stress

Results are printed and saved to ``output/stress-display.json``. The runner
times out after ``30 + 3 * cycles`` seconds to detect hangs. Larger decks or
slower hardware may require smaller workloads. Keep the same hardware, Chrome
version and workload when comparing results. DOM bounds detect retained visible
content; they do not establish that detached objects or GPU resources are freed.

Running application workload
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Start a separate rehearsal instance/profile. For a disposable portable profile,
create a directory and launch from the repository root::

    mkdir -p output/stress-profile/Data
    .venv/bin/python run_opal_presenter.py --portable --portable-path "$PWD/output/stress-profile"

Complete first-run setup, enable the remote API, and prepare a rehearsal service
containing songs with long text/Unicode/chords, images, PDFs, short and long
videos, and presentations in the formats used in production. Use representative
media resolutions and a service/library at least as large as a normal event.
Send a valid item live before enabling control. Ensure media items auto-play if
that is the production behaviour. Avoid other operators during a measured run.

With the application running, simulate eight remote viewers, each making two
requests per second, for a minute::

    .venv/bin/python scripts/stress_remote.py --duration 60 --clients 8 --rate 2

This default mode only reads system information, service items and live slides.
The total requested rate is ``clients * rate``; each client rotates through the
four endpoints. Requests slow down rather than accumulating an unbounded queue
when the application cannot keep up.

Add a single operator to switch service items and visit first/last slides::

    .venv/bin/python scripts/stress_remote.py --control --duration 600 --operator-interval 8 --max-p95-ms 5000

``--control`` changes the live output, starts media/presentation items according
to their service settings, and may create normal song-usage records. Use it only
with rehearsal data and outputs. It attempts to restore the original item and
slide at the end, and reports restoration failures. It cannot restore video
position, external presentation state or undo usage records. It skips invalid
service items. Each command must reach the requested live item/slide within
``--timeout`` seconds (default 5); HTTP success alone is insufficient.

For an endurance run, raise ``--duration`` to ``7200``. For a burst scenario,
raise ``--clients`` and ``--rate``. Use ``--url`` for a different API address and
``--report`` to keep separate reports. If authentication is enabled, set
``OPAL_STRESS_USERNAME`` and ``OPAL_STRESS_PASSWORD`` in the environment,
or supply an existing token in ``OPAL_STRESS_TOKEN``. Credentials are not
included in reports. Use trusted local/rehearsal connections for credentials.

The JSON report at ``output/stress-remote.json`` includes counts, failures,
median, p95 and maximum latency per operation. Latency percentiles use the most
recent 10,000 samples per operation; counts and maximum cover the entire run.
The operator metric includes dispatch and confirmation. Errors, confirmation
timeouts and p95 latencies over ``--max-p95-ms`` produce a non-zero exit status.
A slow or hung app will produce request/confirmation failures; a process crash
will produce connection failures. These symptoms do not identify the root cause.
Ctrl+C stops the clients after in-flight requests, attempts restoration in
control mode, and writes a failed report marked ``cancelled``.

Watch the real output and operator UI while testing. The API confirms controller
state, but cannot prove that PowerPoint/Keynote/LibreOffice actually displayed
the right frame, that audio stayed synchronised, or that the Qt UI remained
responsive. Check those on the target Windows/macOS/Linux machine with the
actual presentation backend, GPU, codecs and output screens. Watch CPU and
memory in the system monitor, check the application log, and retain the report
and workload alongside any recording of a visible problem. Native backends and
hardware must be checked independently of a successful browser test.

The driver's own regression checks use a temporary localhost HTTP server::

    .venv/bin/python -m pytest -q tests/stress/test_remote_stress.py
