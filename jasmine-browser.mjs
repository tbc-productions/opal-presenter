import path from 'node:path';
import {readdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import serveStatic from 'serve-static';

const projectDir = path.dirname(fileURLToPath(import.meta.url));

export default {
  srcDir: '.',
  srcFiles: [
    'tests/js/fake_webchannel.js',
    'opal/core/display/html/reveal.js',
    'opal/core/display/html/display-init.js',
    'opal/core/display/html/display.js'
  ],
  specDir: 'tests/js',
  specFiles: readdirSync(path.join(projectDir, 'tests/js'))
    .filter(name => /^test_.*\.js$/.test(name)).sort(),
  env: {
    // These legacy specs share a Display singleton and retain their file order.
    random: false,
    forbidDuplicateNames: true
  },
  listenAddress: 'localhost',
  hostname: 'localhost',
  browser: {name: 'headlessChrome'},
  middleware: {
    // Keep iframe rendering fixtures at the same URLs as the previous runner.
    '/base/opal/core/display/html': serveStatic(path.join(projectDir, 'opal/core/display/html')),
    '/base/tests/js': serveStatic(path.join(projectDir, 'tests/js'))
  }
};
