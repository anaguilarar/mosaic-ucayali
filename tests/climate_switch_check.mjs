/* Regression check: switching climate variables must reset the render scale/mode.
   Bug it guards (2026-10-23): Precipitation->Anomaly then Drought (SPI-3) rendered SPI with the
   anomaly normalisation still applied, clamping every cell to BrBG's darkest brown (2 distinct
   colours instead of hundreds).
   Paths checked, counting distinct fill colours in the climate-grid source:
     1. precip -> anomaly -> SPI-3 (expect > 100 colours at the latest month, latest month)
     2. SPI-3 -> precip + anomaly   (reverse path)
     3. -> temperature              (value mode)
   Usage: node tests/climate_switch_check.mjs   (dev server on http://127.0.0.1:8765/site/) */
import { Browser, sleep } from './lib/cdp.mjs';

const URL_ = (process.env.APP_URL || 'http://127.0.0.1:8765/site/');
const COUNT = `(() => {
  const feats = window.__map.querySourceFeatures('climate-grid');
  const cols = new Set();
  for (const f of feats) { const c = f.properties?.c; if (c && c !== 'rgba(0,0,0,0)') cols.add(c); }
  return cols.size;
})()`;
const click = (sel) => `(() => { const n = document.querySelector(${JSON.stringify(sel)}); if (!n) return 'missing ' + ${JSON.stringify(sel)}; n.click(); return 'ok'; })()`;
/* the draw is async (tif fetch + setData + tile render): poll until the colour count settles */
async function settledCount(page) {
  let last = -1;
  for (let i = 0; i < 20; i++) {
    await sleep(700);
    const n = await page.eval(COUNT).catch(() => 0);
    if (n > 0 && n === last) return n;
    last = n;
  }
  return last;
}

let failed = 0;
const expectOver = (name, n, min = 100) => {
  const ok = n > min;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}: ${n} distinct colours (need > ${min})`);
  if (!ok) failed++;
};

const browser = await Browser.launch({ width: 1440, height: 900 });
try {
  const page = await browser.newPage({ width: 1440, height: 900 });
  await page.send('Runtime.enable');
  browser.on(page.sessionId, 'Runtime.exceptionThrown', (p) =>
    console.log('EXC:', p.exceptionDetails.text));
  await page.goto(URL_, { timeoutMs: 30000, settleMs: 800 });
  await page.eval(`new Promise((res) => { const m = window.__map; m.once('idle', () => res('i')); setTimeout(() => res('t'), 20000); })`);

  // 1. precip -> anomaly -> SPI-3 (the reported path)
  console.log(await page.eval(click('.rail .item[data-overlay="precip"]')), 'precip');
  await sleep(2500);
  console.log(await page.eval(click('#segMode button[data-v="anomaly"]')), 'anomaly');
  expectOver('precip anomaly (sanity)', await settledCount(page), 50);
  console.log(await page.eval(click('.rail .item[data-overlay="spi3"]')), 'spi3');
  const spiN = await settledCount(page);
  console.log('   SPI month shown:', await page.eval(`document.querySelector('#timeLabel')?.textContent || ''`));
  expectOver('SPI-3 after precip anomaly', spiN);

  // 2. reverse: SPI-3 -> precip, re-select anomaly
  console.log(await page.eval(click('.rail .item[data-overlay="precip"]')), 'precip again');
  await sleep(2000);
  console.log(await page.eval(click('#segMode button[data-v="anomaly"]')), 'anomaly again');
  expectOver('precip anomaly after SPI-3', await settledCount(page));

  // 3. temperature. Anomaly legitimately sticks (tmean has normals) and its 0.1-degree quantisation
  // gives few distinct colours, so count the VALUE mode, which must span the magma ramp.
  console.log(await page.eval(click('.rail .item[data-overlay="temperature"]')), 'temperature');
  await sleep(1500);
  console.log(await page.eval(click('#segMode button[data-v="value"]')), 'value mode');
  expectOver('temperature (value) after precip anomaly', await settledCount(page));

  await page.close();
} finally {
  await browser.close();
}
process.exit(failed ? 1 : 0);
