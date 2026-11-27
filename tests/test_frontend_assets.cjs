const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync, existsSync} = require('node:fs');
const {resolve, join} = require('node:path');
const {Script} = require('node:vm');

const frontend = resolve(__dirname, '..', 'frontend');
const html = readFileSync(join(frontend, 'index.html'), 'utf8');

test('GitHub Pages package includes valid local scripts, styles and exchange rates', () => {
  const assets = [...html.matchAll(/(?:src|href)="([^"#][^"]*)"/g)].map(match => match[1])
    .filter(url => !/^[a-z]+:|^\/\//i.test(url)).map(url => url.split(/[?#]/)[0]);
  assert.ok(assets.includes('analytics-ui.js'));
  assert.ok(assets.includes('analytics-fx.js'));
  for (const asset of assets) {
    assert.ok(!asset.startsWith('/'), `${asset} must work under the repository Pages path`);
    const path = join(frontend, asset);
    assert.ok(existsSync(path), `Missing published asset: ${asset}`);
    if (asset.endsWith('.js')) new Script(readFileSync(path, 'utf8'), {filename: asset});
  }
  const snapshot = JSON.parse(readFileSync(join(frontend, 'data/exchange-rates.json'), 'utf8'));
  assert.equal(snapshot.base, 'EUR');
  assert.equal(snapshot.rates.EUR, 1);
  assert.match(snapshot.date, /^\d{4}-\d{2}-\d{2}$/);
  for (const [currency, rate] of Object.entries(snapshot.rates)) {
    assert.match(currency, /^[A-Z]{3}$/);
    assert.ok(Number.isFinite(rate) && rate > 0, `Invalid rate for ${currency}`);
  }
});
