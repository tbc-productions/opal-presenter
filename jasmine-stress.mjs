import {mkdirSync, writeFileSync} from 'node:fs';
import config from './jasmine-browser.mjs';
import serveStatic from 'serve-static';

function positive(name, fallback, integer = false) {
  const value = Number(process.env[name] ?? fallback);
  if (!Number.isFinite(value) || value <= 0 || (integer && !Number.isInteger(value))) {
    throw new Error(`${name} must be a positive ${integer ? 'integer' : 'number'}`);
  }
  return value;
}

const settings = {
  cycles: positive('STRESS_CYCLES', 100, true),
  slides: positive('STRESS_SLIDES', 30, true),
  p95BudgetMs: positive('STRESS_P95_MS', 500)
};

export default {
  ...config,
  specDir: 'tests/stress',
  specFiles: ['display_stress.js'],
  middleware: {
    ...config.middleware,
    '/base/tests/resources/media': serveStatic('tests/resources/media'),
    '/stress-settings': (_req, res) => {
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify(settings));
    }
  },
  reporters: [{
    specDone(result) {
      mkdirSync('output', {recursive: true});
      const report = {passed: result.status === 'passed', ...result.properties?.stress,
        failures: result.failedExpectations.map(failure => failure.message)};
      writeFileSync('output/stress-display.json', JSON.stringify(report, null, 2) + '\n');
      console.log(JSON.stringify(report, null, 2));
    }
  }]
};
