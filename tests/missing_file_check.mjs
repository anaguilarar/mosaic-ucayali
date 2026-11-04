/* What the app shows when an optional data file is missing. Renames the file temporarily, loads the
   app, records exceptions, failed requests, the rail, the two drawer tabs and a veg-class click, then
   restores the file.
   Usage: node tests/missing_file_check.mjs <outdir> [baseline|veg_classes|story_chapters|studies]
   (APP_URL env var overrides the local dev-server URL) */
import { renameSync, existsSync } from 'node:fs';
import { Browser, sleep } from './lib/cdp.mjs';

const OUT = process.argv[2], CASE = process.argv[3] || 'baseline';
const FILES = { veg_classes: 'vectors/veg_classes.geojson',
                story_chapters: 'meta/story_chapters.json', studies: 'meta/studies.json' };
const DATA = new URL('../data/', import.meta.url).pathname.replace(/^\/([A-Z]:)/, '$1');
const f = FILES[CASE] && decodeURIComponent(DATA + FILES[CASE]);
const hid = f && existsSync(f);
if (hid) renameSync(f, f + '.hidden');
else if (f) console.log('note:', FILES[CASE], 'does not exist yet - case behaves like baseline');
const browser = await Browser.launch({ width: 1440, height: 900 });
const NL = 'String.fromCharCode(10)';
try {
  const page = await browser.newPage({ width: 1440, height: 900 });
  await page.send('Runtime.enable'); await page.send('Network.enable');
  browser.on(page.sessionId, 'Runtime.exceptionThrown', (p) => console.log('EXCEPTION:', p.exceptionDetails.exception?.description?.split('\n')[0] || p.exceptionDetails.text));
  browser.on(page.sessionId, 'Network.responseReceived', (p) => { if (p.response.status >= 400) console.log('HTTP', p.response.status, p.response.url.split('/data/')[1] || p.response.url); });
  browser.on(page.sessionId, 'Runtime.consoleAPICalled', (p) => { if (p.type === 'error' || p.type === 'warning') console.log('console.' + p.type + ':', (p.args || []).map((a) => a.value ?? a.description).join(' ').slice(0, 200)); });
  await page.goto((process.env.APP_URL || 'http://127.0.0.1:8765/site/'), { timeoutMs: 30000, settleMs: 9000 });
  await page.screenshot({ path: `${OUT}/${CASE}_map.jpg` });
  console.log('rail items:', await page.eval(`JSON.stringify([...document.querySelectorAll('.rail .item')].map((n) => n.innerText.split(${NL}).join(' ')))`));
  // veg classes: rail state and (if present) a polygon click
  console.log('veg item:', await page.eval(`(document.querySelector('.rail .item[data-overlay="veg_classes"]')?.innerText || 'none').split(${NL}).join(' | ')`));
  if (CASE !== 'veg_classes') {
    await page.eval(`void document.querySelector('.rail .item[data-overlay="veg_classes"]')?.click()`); await sleep(1500);
    await page.eval(`void window.__map.jumpTo({ center: [-75.26, -8.96], zoom: 12 })`); await sleep(2500);
    await page.eval(`void (() => { const m = window.__map, ll = { lng: -75.2622, lat: -8.9619 }; m.fire('click', { lngLat: ll, point: m.project(ll), originalEvent: {} }); })()`);
    await sleep(1200);
    console.log('veg click popup:', await page.eval(`(document.querySelector('.popover:not([hidden])')?.innerText || '-').split(${NL}).filter(Boolean).join(' | ').slice(0, 260)`));
    console.log('legend:', await page.eval(`(document.querySelector('#legend:not([hidden])')?.innerText || '-').split(${NL}).filter(Boolean).slice(0, 4).join(' | ')`));
    await page.screenshot({ path: `${OUT}/${CASE}_veg.jpg` });
  }
  // the Story and Studies tabs (what each shows when its file is missing)
  await page.eval(`void document.querySelector('#storiesBtn').click()`); await sleep(1500);
  for (const name of ['Story', 'Studies']) {
    await page.eval(`void [...document.querySelectorAll('#storiesPanel button')].find((x) => x.textContent.trim() === '${name}')?.click()`); await sleep(1200);
    console.log(`${name} tab:`, await page.eval(`(document.querySelector('#storiesBody')?.innerText || 'none').split(${NL}).filter(Boolean).slice(0, 3).join(' | ').slice(0, 200)`),
      '| chapters', await page.eval(`String(document.querySelectorAll('#storiesBody .chapter').length)`),
      '| cards', await page.eval(`String(document.querySelectorAll('#storiesBody .story-card').length)`));
    await page.screenshot({ path: `${OUT}/${CASE}_tab_${name}.jpg` });
  }
  // About panel renders from the registry
  await page.eval(`void document.querySelector('#storiesClose').click()`);
  await page.eval(`void document.querySelector('#aboutBtn').click()`); await sleep(800);
  console.log('about blocks:', await page.eval(`String(document.querySelectorAll('#aboutBody .chart-block').length)`));
} finally {
  await browser.close();
  if (hid) { renameSync(f + '.hidden', f); console.log('restored', FILES[CASE], existsSync(f)); }
}
