/* Story walk-through: open the Uses & studies drawer, scroll every chapter into the trigger band,
   and record per chapter: the active overlay(s), pending pill, chart/figure rendering and the
   first number block. Then the Studies tab: expand every card. Exits 1 on any page exception.
   Usage: node tests/story_check.mjs [url] (APP_URL env var also works) */
import { Browser, sleep } from './lib/cdp.mjs';

const URL_ = process.argv[2] || process.env.APP_URL || 'http://127.0.0.1:8765/site/';
const NL = 'String.fromCharCode(10)';
const browser = await Browser.launch({ width: 1440, height: 900 });
let exc = 0;
try {
  const page = await browser.newPage({ width: 1440, height: 900 });
  await page.send('Runtime.enable');
  browser.on(page.sessionId, 'Runtime.exceptionThrown', (p) => { exc++; console.log('EXC', (p.exceptionDetails.exception?.description || p.exceptionDetails.text).split('\n')[0]); });
  await page.goto(URL_, { timeoutMs: 45000, settleMs: 3000 });
  for (let i = 0; i < 40; i++) { if (await page.eval(`String(!!window.__map && window.__map.loaded())`) === 'true') break; await sleep(500); }
  for (let i = 0; i < 20; i++) {
    await page.eval(`void (document.querySelector('#storiesPanel').hidden && document.querySelector('#storiesBtn').click())`); await sleep(600);
    if (await page.eval(`String(document.querySelectorAll('.chapter').length)`) !== '0') break;
  }
  const ids = JSON.parse(await page.eval(`JSON.stringify([...document.querySelectorAll('.chapter')].map((c) => c.dataset.id))`));
  console.log('chapters:', ids.length, ids.join(' '));
  const MAPSTATE = `(() => { const on = [...document.querySelectorAll('.rail .item[aria-pressed="true"]')].map((n) => n.dataset.overlay).filter(Boolean);
    const m = window.__map, c = m.getCenter();
    return 'overlay=' + (on.join(',') || '-') + ' c=' + c.lng.toFixed(1) + ',' + c.lat.toFixed(1) + ' z=' + m.getZoom().toFixed(1); })()`;
  for (const [n, id] of ids.entries()) {
    await page.eval(`void (() => { const b = document.querySelector('#storiesBody'), c = document.querySelector('.chapter[data-id="${id}"]');
      b.scrollTop += c.getBoundingClientRect().top - b.getBoundingClientRect().top - b.clientHeight * 0.25; })()`);
    await sleep(2300);
    for (let i = 0; i < 12; i++) { if (await page.eval(`String(window.__map.loaded() && !window.__map.isMoving())`) === 'true') break; await sleep(500); }
    const info = await page.eval(`(() => { const c = document.querySelector('.chapter[data-id="${id}"]');
      const pill = c.querySelector('.pill')?.textContent || '';
      const chart = c.querySelector('.chapter-chart') ? (c.querySelector('.chapter-chart svg') ? 'chart ok' : 'CHART EMPTY') : '';
      const nums = c.querySelectorAll('.story-num').length;
      return [pill, chart, nums + ' numbers'].filter(Boolean).join(' · '); })()`);
    console.log(`ch ${String(n + 1).padStart(2)} ${id.padEnd(12)}:`, await page.eval(MAPSTATE), '|', info);
  }
  // studies tab: expand every card
  await page.eval(`void [...document.querySelectorAll('#storiesPanel button')].find((x) => x.textContent.trim() === 'Studies')?.click()`); await sleep(1200);
  const nCards = +await page.eval(`String(document.querySelectorAll('#storiesBody .story-card').length)`);
  console.log('cards:', nCards);
  for (let i = 0; i < nCards; i++) {
    await page.eval(`void document.querySelectorAll('#storiesBody .story-card .story-head')[${i}]?.click()`); await sleep(800);
    console.log(' card', i + 1, ':', await page.eval(`(document.querySelectorAll('#storiesBody .story-card')[${i}]?.innerText || '-').split(${NL}).filter(Boolean).slice(0, 2).join(' | ').slice(0, 130)`));
  }
} finally { await browser.close(); }
console.log(exc, 'exception(s)');
process.exit(exc ? 1 : 0);
