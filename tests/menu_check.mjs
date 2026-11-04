/* Narrow-window layer menu: at ~800 px and phone width, open the menu with ☰, switch a layer, close it again
   with ☰ (real mouse/touch events at the button's position), and check the map is uncovered.
   Usage: node tests/menu_check.mjs [url] [outdir] */
import { Browser, sleep } from './lib/cdp.mjs';

const URL_ = process.argv[2] || process.env.APP_URL || 'http://127.0.0.1:8765/site/';
const OUT = process.argv[3] || '.';
const browser = await Browser.launch({ width: 1440, height: 900 });
let fails = 0;
const tap = async (page, sel) => {
  const r = JSON.parse(await page.eval(`JSON.stringify((() => { const b = document.querySelector('${sel}').getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; })())`));
  const top = await page.eval(`(() => { const e = document.elementFromPoint(${r[0]}, ${r[1]}); return e ? (e.id || e.className?.baseVal || e.className || e.tagName) + ' in ' + (e.closest('[id]')?.id || '-') : 'none'; })()`);
  for (const type of ['mousePressed', 'mouseReleased']) await page.send('Input.dispatchMouseEvent', { type, x: r[0], y: r[1], button: 'left', clickCount: 1 });
  await sleep(600);
  return top;
};
const state = (page) => page.eval(`(() => { const sb = document.querySelector('#sidebar'), b = sb.getBoundingClientRect(), m = document.querySelector('#map').getBoundingClientRect();
  const cx = m.x + m.width / 2, cy = m.y + m.height / 2, e = document.elementFromPoint(cx, cy);
  return 'open=' + sb.classList.contains('open') + ' aria=' + document.querySelector('#menuBtn').getAttribute('aria-expanded') +
    ' sidebarLeft=' + Math.round(b.left) + ' mapCentreHit=' + (e?.closest('#map') ? 'map' : (e?.closest('[id]')?.id || e?.tagName)); })()`);
try {
  for (const [w, h, mobile] of [[800, 900, false], [390, 844, true]]) {
    const page = await browser.newPage({ width: w, height: h, mobile });
    await page.send('Runtime.enable');
    if (process.env.LOCAL_SITE) {   // test unpublished changes: serve the live page's site/js and site/css from this folder
      const fs = await import('node:fs');
      await page.send('Fetch.enable', { patterns: [{ urlPattern: '*/site/js/*' }, { urlPattern: '*/site/css/*' }] });
      browser.on(page.sessionId, 'Fetch.requestPaused', (p) => {
        const rel = new URL(p.request.url).pathname.split('/site/')[1], f = process.env.LOCAL_SITE + '/' + rel;
        const type = rel.endsWith('.css') ? 'text/css' : 'text/javascript';
        page.send('Fetch.fulfillRequest', { requestId: p.requestId, responseCode: 200, responseHeaders: [{ name: 'Content-Type', value: type }],
          body: fs.readFileSync(f).toString('base64') }).catch(() => {});
      });
    }
    await page.goto(URL_, { timeoutMs: 45000, settleMs: 6000 });
    console.log(`--- ${w}x${h}`);
    console.log('start           :', await state(page));
    console.log('tap ☰ (hit ' + await tap(page, '#menuBtn') + ')');
    console.log('after open      :', await state(page));
    await page.screenshot({ path: `${OUT}/menu_${w}_open.jpg` });
    console.log('tap layer (hit ' + await tap(page, '.rail .item[data-overlay="veg_classes"]') + ')');
    console.log('after layer     :', await state(page));
    if (w <= 480) await tap(page, '#menuBtn');   // on a phone choosing a layer closes the menu: reopen it first
    console.log('tap ☰ (hit ' + await tap(page, '#menuBtn') + ')');
    const s = await state(page);
    console.log('after close     :', s);
    if (!/open=false .*mapCentreHit=map/.test(s)) fails++;
    await page.screenshot({ path: `${OUT}/menu_${w}_closed.jpg` });
    // the other ways to close it: Escape, and a tap on the map beside the drawer (wide enough windows only)
    await tap(page, '#menuBtn');
    await page.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
    await page.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
    await sleep(600);
    console.log('open, Escape    :', await state(page));
    if (w > 480) {
      await tap(page, '#menuBtn');
      for (const type of ['mousePressed', 'mouseReleased']) await page.send('Input.dispatchMouseEvent', { type, x: w - 60, y: h / 2, button: 'left', clickCount: 1 });
      await sleep(800);
      console.log('open, map tap   :', await state(page));
    }
    await page.close();
  }
} finally { await browser.close(); }
console.log(fails ? `FAIL (${fails})` : 'OK');
process.exit(fails ? 1 : 0);
