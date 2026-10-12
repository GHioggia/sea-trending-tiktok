const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(require('node:path').join(__dirname, '..', 'index.html'), 'utf8');
const source = html.split('<script>')[1].split('</script>')[0].split('// Init: load dates')[0];

function app(fetch) {
  const elements = new Map();
  const context = {
    fetch, console,
    document: {
      getElementById(id) {
        if (!elements.has(id)) elements.set(id, {textContent:'', innerHTML:'', style:{},
          classList:{values:new Set(), add(v){this.values.add(v)}, remove(v){this.values.delete(v)}}});
        return elements.get(id);
      }
    }
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  context.render = () => { context.rendered = context.DATA; };
  return {context, elements};
}
function reply(status, value) {
  return {status, ok:status>=200 && status<300, json:async()=>value};
}
const report = date => ({date, all:{all:'**真实结果占位测试**'}});
const videos = [{id:'fixture', r:'ID', cat:'gaming'}];

test('404 shows missing AI analysis while retaining video display', async () => {
  const {context:c, elements:e} = app(async url => reply(url.includes('insights') ? 404 : 200, videos));
  const pending = c.loadDate('2026-10-05');
  assert.match(e.get('insight-text').textContent, /正在加载/);
  await pending;
  assert.equal(c.INSIGHT_STATUS, 'missing');
  assert.match(e.get('insight-text').textContent, /本期周报尚未提供AI分析/);
  assert.ok(e.get('insight-panel').classList.values.has('visible'));
  assert.equal(c.DATA, videos);
});
for (const kind of ['500', 'network', 'malformed', 'wrong-date', 'null']) {
  test(kind + ' shows retry message and still renders videos', async () => {
    const {context:c, elements:e} = app(async url => {
      if (!url.includes('insights')) return reply(200, videos);
      if (kind === '500') return reply(500);
      if (kind === 'network') throw new Error('offline');
      if (kind === 'malformed') return {ok:true, status:200, json:async()=>{throw new Error('bad JSON')}};
      return reply(200, kind === 'null' ? null : report('2026-09-14'));
    });
    await c.loadDate('2026-10-05');
    assert.equal(c.INSIGHT_STATUS, 'error');
    assert.match(e.get('insight-text').textContent, /加载失败/);
    assert.equal(c.rendered, videos);
  });
}
test('valid insights render markdown; unavailable dimension shows explicit message', async () => {
  const {context:c, elements:e} = app(async url => reply(200, url.includes('insights') ? report('2026-10-05') : videos));
  await c.loadDate('2026-10-05');
  assert.equal(c.INSIGHT_STATUS, 'ready');
  assert.match(e.get('insight-text').innerHTML, /<strong>/);
  c.curPrimary = 'TH';
  c.updateInsight();
  assert.match(e.get('insight-text').textContent, /当前地区和分类暂无AI分析/);
  assert.ok(e.get('insight-panel').classList.values.has('visible'));
});
test('older responses cannot overwrite selected date, including A to B to A', async () => {
  const requests = [];
  const {context:c} = app(url => new Promise(resolve => requests.push({url, resolve})));
  const first = c.loadDate('2026-10-05');
  const second = c.loadDate('2026-09-14');
  const third = c.loadDate('2026-10-05');
  requests[4].resolve(reply(200, report('2026-10-05')));
  requests[5].resolve(reply(200, videos));
  await third;
  requests[2].resolve(reply(404));
  requests[3].resolve(reply(200, [{id:'old-B'}]));
  requests[0].resolve(reply(500));
  requests[1].resolve(reply(200, [{id:'old-A'}]));
  await Promise.all([first, second]);
  assert.equal(c.INSIGHT_STATUS, 'ready');
  assert.equal(c.DATA, videos);
  assert.equal(c.curDateStr, '2026-10-05');
});
