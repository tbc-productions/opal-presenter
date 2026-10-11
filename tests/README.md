# Tests for Opal Presenter

This directory contains unit tests for Opal Presenter.

## Prerequisites

In order to run the unit tests, you will need the following Python packages/libraries installed:

- **pytest**
- **pytestqt**
- **flake8**

On Ubuntu you can install the python3-pytest and flake8 packages.
Most other distributions will also have these packages.
On Windows and Mac OS X you will need to use `pip` to install these packages.

## Running the Tests

To run the tests, navigate to the root directory of the Opal Presenter project, and then run the following command:

```bash
pytest -v tests
```

## JavaScript Tests

The display tests use Jasmine 7 with jasmine-browser-runner. Install Node.js
22 or 24, pnpm and Google Chrome, then run from the project root:

```bash
pnpm install --frozen-lockfile
pnpm test
```

The runner starts a local server and runs the specs in headless Chrome.
Selenium manages the matching ChromeDriver. For interactive debugging, run:

```bash
pnpm test:serve
```

Open the URL printed by the runner in a browser. The configuration in
`jasmine-browser.mjs` also serves the image and stylesheet fixtures used by
the iframe rendering tests. Specs retain their existing execution order because
the existing unit tests share one Display singleton.

## Production stress tests

The stress tests are opt-in and use the existing Python and browser test
dependencies. They complement the regression suite; a passing run covers the
workload and machine tested, rather than guaranteeing every glitch is absent.

### Display workload

Run repeated songs, images, PDF-style image slides and actual MP4 playback:

```bash
pnpm test:stress
```

If pnpm tries to reinstall an already working dependency tree, invoke the
installed runner directly:

```bash
node node_modules/jasmine-browser-runner/bin/jasmine-browser-runner runSpecs --config=jasmine-stress.mjs
```

- **Default workload:** replaces 100 items, with 30 slides per non-video item,
  using real Display and Reveal code in headless Chrome.
- **Coverage:** selected content, footers, image backgrounds, decoded video progress,
  pause/stop, blank/show, resizing and transition cleanup.
- **Failure conditions:** browser errors, unexpected DOM growth or 95th-percentile
  deck-render latency above 500 ms.
- **Render timing:** ends after image readiness and two animation frames; excludes
  the remaining transition duration and video playback checks.
- **Scope:** Python web-channel callbacks are substituted; Qt and native presentations
  are not exercised.

Change the workload and latency budget, for example:

```bash
STRESS_CYCLES=1000 STRESS_SLIDES=120 STRESS_P95_MS=500 pnpm test:stress
```

- **Results:** printed and saved to `output/stress-display.json`.
- **Hang detection:** the runner times out after `30 + 3 * cycles` seconds.
- **Workload sizing:** larger decks or slower hardware may require smaller workloads.
- **Comparisons:** keep hardware, Chrome version and workload the same.
- **Memory limits:** DOM bounds detect retained visible content; they do not establish
  that detached objects or GPU resources are freed.

### Running application workload

Start a separate rehearsal instance/profile. For a disposable portable profile,
create a directory and launch from the repository root:

```bash
mkdir -p output/stress-profile/Data
.venv/bin/python run_opal_presenter.py --portable --portable-path "$PWD/output/stress-profile"
```

Prepare the rehearsal instance:

1. Complete first-run setup and enable the remote API.
2. Prepare a service containing songs with long text/Unicode/chords, images, PDFs,
   short and long videos, and presentations in the formats used in production.
3. Use representative media resolutions and a service/library at least as large
   as a normal event.
4. Send a valid item live before enabling control. Ensure media items auto-play
   if that is the production behaviour.
5. Avoid other operators during a measured run.

With the application running, simulate eight remote viewers, each making two
requests per second, for a minute:

```bash
.venv/bin/python scripts/stress_remote.py --duration 60 --clients 8 --rate 2
```

This default mode only reads system information, service items and live slides.
The total requested rate is `clients * rate`; each client rotates through the
four endpoints. Requests slow down rather than accumulating an unbounded queue
when the application cannot keep up.

Add a single operator to switch service items and visit first/last slides:

```bash
.venv/bin/python scripts/stress_remote.py --control --duration 600 --operator-interval 8 --max-p95-ms 5000
```

- **Control mode:** `--control` changes live output, starts media/presentation items
  according to service settings and may create normal song-usage records. Use only
  rehearsal data and outputs.
- **Restoration:** attempts to restore the original item and slide at the end and
  reports failures. Cannot restore video position, external presentation state or
  undo usage records.
- **Invalid items:** skipped.
- **Confirmation:** each command must reach the requested live item/slide within
  `--timeout` seconds (default 5). HTTP success alone is insufficient.

- **Endurance:** raise `--duration` to `7200`.
- **Burst:** raise `--clients` and `--rate`.
- **API address:** use `--url`.
- **Separate reports:** use `--report`.
- **Authentication:** set `OPAL_STRESS_USERNAME` and `OPAL_STRESS_PASSWORD`, or supply
  an existing token in `OPAL_STRESS_TOKEN`. Credentials are excluded from reports;
  use trusted local/rehearsal connections.

The JSON report is saved to `output/stress-remote.json`:

- **Metrics:** counts, failures, median, p95 and maximum latency per operation.
- **Sample window:** percentiles use the most recent 10,000 samples per operation;
  counts and maximum cover the entire run.
- **Operator latency:** includes dispatch and confirmation.
- **Exit status:** errors, confirmation timeouts and p95 latency over `--max-p95-ms`
  produce a non-zero status.
- **Failure symptoms:** a slow or hung app produces request/confirmation failures;
  a process crash produces connection failures. These do not identify the root cause.
- **Ctrl+C:** stops clients after in-flight requests, attempts restoration in control
  mode and writes a failed report marked `cancelled`.

Watch the real output and operator UI while testing:

- **Native output:** the API confirms controller state, but cannot prove that
  PowerPoint/Keynote/LibreOffice displayed the right frame, audio stayed synchronised
  or the Qt UI remained responsive.
- **Target hardware:** check on Windows/macOS/Linux with the actual presentation
  backend, GPU, codecs and output screens. Native backends and hardware must be
  checked independently of a successful browser test.
- **Evidence:** watch CPU and memory in the system monitor, check the application
  log, and retain the report and workload alongside any recording of a visible problem.

The driver's own regression checks use a temporary localhost HTTP server:

```bash
.venv/bin/python -m pytest -q tests/stress/test_remote_stress.py
```
