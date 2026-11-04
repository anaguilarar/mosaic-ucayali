/* A scripted ~5-minute session for measuring data requests (count them in the prep/serve.py log):
   load; pan/zoom around the basin and the Winam Gulf; switch every layer once with a click popup on each;
   scroll the whole story.  Usage: node tests/request_session.mjs [url] [--no-terrain-wait] [--pan-only]
   (default url: local dev server). --no-terrain-wait moves the map straight after load (reproduces the MapLibre
   5.6.0 terrain error); --pan-only stops after the pan/zoom part. */
import { Browser, sleep } from './lib/cdp.mjs';

const ARGS = process.argv.slice(2), FLAGS = ARGS.filter((a) => a.startsWith('--'));
const URL_ = ARGS.find((a) => !a.startsWith('--')) || 'http://127.0.0.1:8765/site/';
const NO_WAIT = FLAGS.includes('--no-terrain-wait'), PAN_ONLY = FLAGS.includes('--pan-only');
const idle = `new Promise((res) => { const m = window.__map; m.once('idle', () => res('idle')); setTimeout(() => res('timeout'), 4000); })`;
const t0 = Date.now(), stamp = () => `${((Date.now() - t0) / 1000).toFixed(0)}s`;
const browser = await Browser.launch({ width: 1440, height: 900 });
try {
  const page = await browser.newPage({ width: 1440, height: 900 });
  await page.send('Runtime.enable'); await page.send('Network.enable');
  const hosts = {};
  browser.on(page.sessionId, 'Network.requestWillBeSent', (p) => { const h = new URL(p.request.url).host; hosts[h] = (hosts[h] || 0) + 1; });
  const failed = {}, statusByHost = {};
  browser.on(page.sessionId, 'Network.responseReceived', (p) => { const u = new URL(p.response.url), k = u.host + ' ' + p.response.status;
    statusByHost[k] = (statusByHost[k] || 0) + 1;
    if (p.response.status >= 400 && !u.pathname.endsWith('favicon.ico')) failed[p.response.status + ' ' + u.host + u.pathname] = (failed[p.response.status + ' ' + u.host + u.pathname] || 0) + 1; });
  browser.on(page.sessionId, 'Network.loadingFailed', (p) => { if (!p.canceled) failed['net ' + p.errorText] = (failed['net ' + p.errorText] || 0) + 1; });
  const consoleErr = [];
  await page.send('Log.enable').catch(() => {});
  browser.on(page.sessionId, 'Runtime.consoleAPICalled', (p) => { if (p.type === 'error') consoleErr.push((p.args || []).map((a) => a.value ?? a.description).join(' ').slice(0, 160)); });
  browser.on(page.sessionId, 'Log.entryAdded', (p) => { if (p.entry.level === 'error' && !/favicon/.test(p.entry.url || '')) consoleErr.push('log: ' + p.entry.text.slice(0, 160)); });
  let exc = 0;
  browser.on(page.sessionId, 'Runtime.exceptionThrown', (p) => { exc++; const d = p.exceptionDetails;
    if (exc <= 2) console.log(stamp(), 'EXC:', (d.exception?.description || d.text).split('\n').slice(0, 8).join(' / '), '|',
      (d.stackTrace?.callFrames || []).slice(0, 6).map((f) => `${f.functionName || '(anon)'}@${f.url.split('/').pop()}:${f.lineNumber + 1}:${f.columnNumber + 1}`).join(' < ')); });
  await page.goto(URL_, { timeoutMs: 30000, settleMs: 1000 });
  // wait until the map has loaded and the terrain is ready: a flyTo while terrain tiles are still loading
  // throws in MapLibre (_getOverscaledTileIDFromLngLatZoom, 'wrap') and freezes the render loop
  for (let i = 0; i < 60 && !NO_WAIT; i++) { if (await page.eval(`String(!!window.__map && window.__map.loaded() && window.__map.areTilesLoaded())`) === 'true') break; await sleep(500); }
  console.log(stamp(), 'loaded');

  // pan/zoom: department overview, then Pucallpa, the Aguaytía corridor and around the department
  const views = [[-73.6, -9.5, 6.1], [-74.55, -8.38, 9], [-74.55, -8.38, 11.5], [-74.9, -8.5, 10],
                 [-75.2, -8.83, 10.5], [-75.5, -9.0, 9.5], [-74.3, -9.5, 9], [-73.75, -10.73, 9.5],
                 [-72.8, -10.4, 8.5], [-71.5, -9.9, 8], [-70.9, -9.8, 9], [-72.3, -8.4, 8.5],
                 [-74.0, -7.8, 9], [-73.6, -9.5, 6.5]];
  for (const [lng, lat, zoom] of views) {
    await page.eval(`void window.__map.flyTo({ center: [${lng}, ${lat}], zoom: ${zoom}, duration: 1500 })`);
    await sleep(1600); await page.eval(idle); await sleep(500);
  }
  console.log(stamp(), 'pan/zoom done');
  if (PAN_ONLY) { console.log(exc, 'exception(s)'); process.exit(exc ? 1 : 0); }

  // every layer once, with a click popup near San Alejandro (inside the veg-class polygon cluster)
  await page.eval(`void window.__map.jumpTo({ center: [-75.1, -8.8], zoom: 10.5 })`); await page.eval(idle);
  const items = JSON.parse(await page.eval(`JSON.stringify([...document.querySelectorAll('.rail .item')].map((n, i) => [i, n.dataset.overlay || n.dataset.base || n.id || n.innerText.split(String.fromCharCode(10))[0]]))`));
  for (const [i, name] of items) {
    await page.eval(`void document.querySelectorAll('.rail .item')[${i}].click()`);
    await sleep(600); await page.eval(idle); await sleep(300);
    await page.eval(`void (() => { const m = window.__map, ll = { lng: -75.2622, lat: -8.9619 }; m.fire('click', { lngLat: ll, point: m.project(ll), originalEvent: {} }); })()`);
    await sleep(2500);
    const pop = await page.eval(`(document.querySelector('.popover')?.innerText || '-').split(String.fromCharCode(10))[0].slice(0, 40)`);
    console.log(stamp(), 'layer', name, '| popup:', pop);
    await page.eval(`void document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))`);
  }

  // the whole story (tolerates the no-story-yet fallback)
  for (let i = 0; i < 40; i++) {
    await page.eval(`void (document.querySelector('#storiesPanel').hidden && document.querySelector('#storiesBtn').click())`); await sleep(500);
    if (await page.eval(`String(document.querySelectorAll('.chapter, #storiesBody .empty').length)`) !== '0') break;
  }
  const ids = JSON.parse(await page.eval(`JSON.stringify([...document.querySelectorAll('.chapter')].map((c) => c.dataset.id))`));
  for (const id of ids) {
    await page.eval(`void (() => { const b = document.querySelector('#storiesBody'), c = document.querySelector('.chapter[data-id="${id}"]');
      b.scrollTop += c.getBoundingClientRect().top - b.getBoundingClientRect().top - b.clientHeight * 0.2; })()`);
    await sleep(1500); await page.eval(idle); await sleep(1000);
  }
  console.log(stamp(), 'story done:', ids.length, 'chapters');
  console.log('requests by host (browser side):', JSON.stringify(hosts));
  console.log('responses by host and status:', JSON.stringify(statusByHost));
  console.log('failed requests:', JSON.stringify(failed));
  console.log('console errors:', consoleErr.length, JSON.stringify([...new Set(consoleErr)].slice(0, 8)));
  console.log(exc, 'exception(s)');
} finally { await browser.close(); }
