Tests for OpenLP
================

This directory contains unit tests for OpenLP. The ``functional`` directory contains functional unit tests.

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

To run the tests, navigate to the root directory of the OpenLP project, and then run the following command::

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
