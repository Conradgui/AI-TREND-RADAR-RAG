const fs = require('fs')
const path = require('path')
const zlib = require('zlib')
const { performance } = require('perf_hooks')
const { createRequire } = require('module')

// Reproduction requires the exact benchmark-only packages recorded in the JSON:
// flexsearch@0.8.212 and minisearch@7.2.0. FlexSearch is intentionally not a
// production dependency. Run this script from a temporary clone where both are
// installed, or pass that repository path as argv[2].
const repo = process.argv[2] ? path.resolve(process.argv[2]) : process.cwd()
const req = createRequire(path.join(repo, 'package.json'))
const FlexSearch = req('flexsearch')
const MiniSearch = req('minisearch')
const payload = JSON.parse(fs.readFileSync(path.join(repo, 'digests/search-index.json'), 'utf8'))
const documents = payload.documents

function normalize(s) {
  return String(s ?? '').normalize('NFKC').toLocaleLowerCase('en-US')
    .replace(/[^\p{L}\p{N}]+/gu, ' ').trim().replace(/\s+/g, ' ')
}
function normalizeAliases(s) {
  return normalize(s).replace(/\bopen\s+ai\b/g, 'openai')
}
function segments(s) {
  return normalize(s).match(/\p{Script=Han}+|[\p{L}\p{N}]+/gu) || []
}
function tokenize(s) {
  const out = []
  for (const seg of segments(s)) {
    if (/^\p{Script=Han}+$/u.test(seg)) {
      const chars = [...seg]
      out.push(...chars)
      for (let i = 0; i + 1 < chars.length; i++) out.push(chars[i] + chars[i + 1])
    } else out.push(seg)
  }
  return [...new Set(out)]
}
function latinTokens(s) {
  return segments(s).filter(x => !/^\p{Script=Han}+$/u.test(x))
}
function bodyOf(d) {
  return [d.summary, d.source, d.category, d.action,
    d.display_fields?.recommended_topic, d.display_fields?.reason,
    d.display_fields?.angle, ...(d.display_fields?.evidence || []),
    ...(d.tags || []), ...(d.entities || []), ...(d.aliases || [])].filter(Boolean).join(' ')
}
const benchDocs = documents.map(d => ({
  id: d.occurrence_id,
  contentId: d.content_id,
  title: d.title,
  titleNorm: normalize(d.title),
  titleExact: tokenize(d.title).join(' '),
  titleFuzzy: latinTokens(d.title).join(' '),
  body: bodyOf(d),
  bodyExact: tokenize(bodyOf(d)).join(' '),
  bodyFuzzy: latinTokens(bodyOf(d)).join(' '),
}))
const byId = new Map(benchDocs.map(d => [d.id, d]))

function createFlexIndex() {
  return new FlexSearch.Document({
    document: {
      id: 'id',
      index: [
        { field: 'titleExact', tokenize: 'strict', encoder: FlexSearch.Charset.Exact },
        { field: 'titleFuzzy', tokenize: 'tolerant', encoder: FlexSearch.Charset.Exact },
        { field: 'bodyExact', tokenize: 'strict', encoder: FlexSearch.Charset.Exact },
      ],
    },
  })
}
function buildFlex() {
  const t0 = performance.now()
  const index = createFlexIndex()
  for (const d of benchDocs) index.add(d)
  return { index, ms: performance.now() - t0 }
}

function buildMini() {
  const t0 = performance.now()
  const index = new MiniSearch({
    idField: 'id',
    fields: ['title', 'body'],
    tokenize,
    processTerm: term => term,
    searchOptions: {
      boost: { title: 5, body: 1 },
      combineWith: 'AND',
      fuzzy: false,
    },
  })
  index.addAll(benchDocs)
  return { index, ms: performance.now() - t0 }
}

function uniqueContent(ids, limit = 10) {
  const out = [], seen = new Set()
  for (const id of ids) {
    const d = byId.get(String(id))
    if (!d || seen.has(d.contentId)) continue
    seen.add(d.contentId); out.push(d)
    if (out.length >= limit) break
  }
  return out
}
function exactPromote(query, docs) {
  const q = normalize(query)
  const exact = exactTitleMap.get(q) || []
  if (!exact.length) return docs
  const exactContent = new Set(exact.map(d => d.contentId))
  const promoted = uniqueContent(exact.map(d => d.id), 100)
  return promoted.concat(docs.filter(d => !exactContent.has(d.contentId)))
}
function flexSearch(index, query, alias = true, limit = 10) {
  const q = alias ? normalizeAliases(query) : normalize(query)
  const all = tokenize(q).join(' '), latin = latinTokens(q).join(' ')
  const fields = [
    { field: 'titleExact', query: all, limit: 100 },
    ...(latin ? [{ field: 'titleFuzzy', query: latin, limit: 100 }] : []),
    { field: 'bodyExact', query: all, limit: 100 },
  ]
  const rows = index.search({ index: fields, merge: true, limit: 100, suggest: false })
  return exactPromote(q, uniqueContent(rows.map(r => r.id), 100)).slice(0, limit)
}
function miniSearch(index, query, alias = true, limit = 10) {
  const q = alias ? normalizeAliases(query) : normalize(query)
  let rows = index.search(q, { limit: 100, fuzzy: false })
  if (!rows.length && /^[a-z0-9]+$/i.test(q)) {
    for (let i = 0; i + 1 < q.length; i++) {
      const chars = [...q]
      ;[chars[i], chars[i + 1]] = [chars[i + 1], chars[i]]
      rows = index.search(chars.join(''), { limit: 100, fuzzy: false })
      if (rows.length) break
    }
  }
  if (!rows.length) rows = index.search(q, {
    limit: 100,
    fuzzy: term => (/^[a-z0-9]+$/i.test(term) && term.length >= 5 ? 0.2 : false),
  })
  return exactPromote(q, uniqueContent(rows.map(r => r.id), 100)).slice(0, limit)
}

const contentIds = pred => new Set(benchDocs.filter(pred).map(d => d.contentId))
const titleContains = needle => contentIds(d => d.titleNorm.includes(normalize(needle)))
const searchableContains = needle => contentIds(d => normalize(d.title + ' ' + d.body).includes(normalize(needle)))
const exactGold = title => contentIds(d => d.titleNorm === normalize(title))

const exactTitleMap = new Map()
for (const d of benchDocs) {
  const list = exactTitleMap.get(d.titleNorm) || []
  list.push(d); exactTitleMap.set(d.titleNorm, list)
}
const titleGroups = new Map()
for (const d of benchDocs) {
  if (!titleGroups.has(d.titleNorm)) titleGroups.set(d.titleNorm, d)
}
const uniques = [...titleGroups.values()].filter(d => d.titleNorm.length >= 12)
const zhUnique = uniques.filter(d => /\p{Script=Han}/u.test(d.title)).sort((a,b) => a.title.localeCompare(b.title, 'zh'))
const enUnique = uniques.filter(d => !/\p{Script=Han}/u.test(d.title)).sort((a,b) => a.title.localeCompare(b.title, 'en'))
function evenly(arr, n) {
  const out = []
  for (let i = 0; i < n && arr.length; i++) out.push(arr[Math.floor(i * arr.length / n)])
  return out
}

const cases = []
for (const d of [...evenly(enUnique, 25), ...evenly(zhUnique, 25)]) {
  cases.push({ group: 'exact-title', query: d.title, gold: exactGold(d.title), goldRule: 'normalized_title exact' })
}
for (const [query, canonical] of [
  ['OpenAI','openai'], ['Open AI','openai'], ['openai','openai'],
  ['Claude','claude'], ['Anthropic','anthropic'], ['Claude Code','claude code'],
]) cases.push({ group: 'entity-literal', query, gold: searchableContains(canonical), goldRule: `indexed fields contain ${canonical}` })
for (const query of ['智能体','模型','苹果','谷歌','微软','开源','前端','代码']) {
  cases.push({ group: 'cjk-short', query, gold: searchableContains(query), goldRule: `indexed fields contain ${query}` })
}
for (const [query, canonical] of [
  ['opneai','openai'], ['anthorpic','anthropic'], ['cluade','claude'], ['qdrnt','qdrant'],
  ['langchian','langchain'], ['micorsoft','microsoft'],
]) cases.push({ group: 'typo', query, gold: searchableContains(canonical), goldRule: `indexed fields contain ${canonical}` })
for (const query of ['量子香蕉协议','zyphron quasar protocol','nebulawombat sdk','火星榴莲模型']) {
  cases.push({ group: 'hard-negative', query, gold: new Set(), goldRule: 'no corpus literal / expected empty' })
}

function metrics(search, index) {
  const rows = []
  for (const c of cases) {
    const got = search(index, c.query, true, 10)
    const ranks = got.map((d,i) => c.gold.has(d.contentId) ? i + 1 : 0).filter(Boolean)
    const first = ranks[0] || 0
    const relevant = got.filter(d => c.gold.has(d.contentId)).length
    rows.push({ ...c, got, hit1: first === 1 ? 1 : 0, hit3: first && first <= 3 ? 1 : 0,
      recall10: c.gold.size ? relevant / c.gold.size : null,
      mrr: first ? 1 / first : 0,
      offGold10: c.gold.size ? got.length - relevant : got.length,
      anyNegativeHit: c.gold.size ? null : got.length > 0 ? 1 : 0,
    })
  }
  const groups = {}
  for (const group of [...new Set(rows.map(r => r.group))]) {
    const rr = rows.filter(r => r.group === group), positive = rr.filter(r => r.gold.size)
    groups[group] = {
      n: rr.length,
      hit1: positive.length ? positive.reduce((s,r)=>s+r.hit1,0)/positive.length : null,
      hit3: positive.length ? positive.reduce((s,r)=>s+r.hit3,0)/positive.length : null,
      recall10: positive.length ? positive.reduce((s,r)=>s+r.recall10,0)/positive.length : null,
      mrr: positive.length ? positive.reduce((s,r)=>s+r.mrr,0)/positive.length : null,
      offGoldTop10: rr.reduce((s,r)=>s+r.offGold10,0),
      hardNegativeQueriesWithHits: group === 'hard-negative' ? rr.reduce((s,r)=>s+r.anyNegativeHit,0) : null,
    }
  }
  return { rows, groups }
}

function percentile(a, p) { const s=[...a].sort((x,y)=>x-y); return s[Math.min(s.length-1,Math.floor(p*s.length))] }
function queryTiming(search, index) {
  const queries = cases.map(c=>c.query)
  for (let i=0;i<100;i++) search(index, queries[i%queries.length], true, 10)
  const times=[]
  for (let round=0;round<20;round++) for (const q of queries) {
    const t0=performance.now(); search(index,q,true,10); times.push(performance.now()-t0)
  }
  return { n: times.length, medianMs: percentile(times,.5), p95Ms: percentile(times,.95), meanMs: times.reduce((a,b)=>a+b,0)/times.length }
}
async function flexSerialized(index) {
  const chunks = {}
  await index.export((key, data) => { chunks[key] = data })
  const json = JSON.stringify(chunks)
  const t0 = performance.now()
  const restored = createFlexIndex()
  for (const [k,v] of Object.entries(chunks)) restored.import(k,v)
  const loadMs = performance.now()-t0
  return { bytes:Buffer.byteLength(json), gzipBytes:zlib.gzipSync(json).length, chunks:Object.keys(chunks).length, loadMs,
    smoke:flexSearch(restored,'OpenAI').slice(0,3).map(x=>x.title) }
}
function miniSerialized(index) {
  const json = JSON.stringify(index)
  const t0 = performance.now()
  const restored = MiniSearch.loadJSON(json, {
    idField:'id', fields:['title','body'], tokenize, processTerm:term=>term,
    searchOptions:{boost:{title:5,body:1},combineWith:'AND',fuzzy:false}
  })
  const loadMs=performance.now()-t0
  return { bytes:Buffer.byteLength(json), gzipBytes:zlib.gzipSync(json).length, loadMs,
    smoke:miniSearch(restored,'OpenAI').slice(0,3).map(x=>x.title) }
}
function bundleStats() {
  const files = {
    flexBundle:path.join(repo,'node_modules/.pnpm/flexsearch@0.8.212/node_modules/flexsearch/dist/flexsearch.bundle.module.min.mjs'),
    flexCompact:path.join(repo,'node_modules/.pnpm/flexsearch@0.8.212/node_modules/flexsearch/dist/flexsearch.compact.module.min.js'),
    miniUMD:path.join(repo,'node_modules/.pnpm/minisearch@7.2.0/node_modules/minisearch/dist/umd/index.js'),
    miniES:path.join(repo,'node_modules/.pnpm/minisearch@7.2.0/node_modules/minisearch/dist/es/index.js'),
  }
  return Object.fromEntries(Object.entries(files).map(([k,f])=>{const b=fs.readFileSync(f); return [k,{bytes:b.length,gzipBytes:zlib.gzipSync(b).length}]}))
}

(async()=>{
  const buildTimes={flex:[],mini:[]}; let flex,mini
  for(let i=0;i<5;i++) { let b=buildFlex(); buildTimes.flex.push(b.ms); flex=b.index; b=buildMini(); buildTimes.mini.push(b.ms); mini=b.index }
  const flexEval=metrics(flexSearch,flex), miniEval=metrics(miniSearch,mini)
  const rawSpecial={}
  for(const q of ['OpenAI','Open AI','Claude','Anthropic','智能体','模型','opneai','anthorpic','cluade']) {
    rawSpecial[q]={flex:flexSearch(flex,q,false,5).map(x=>x.title),mini:miniSearch(mini,q,false,5).map(x=>x.title)}
  }
  const audited={}
  for(const q of ['OpenAI','Open AI','Claude','Anthropic','智能体','模型','opneai','anthorpic','cluade','量子香蕉协议']) {
    const c=cases.find(x=>x.query===q)
    audited[q]={goldSize:c?.gold.size, goldRule:c?.goldRule,
      flex:flexSearch(flex,q,true,5).map(x=>({title:x.title,ok:c?.gold.has(x.contentId)})),
      mini:miniSearch(mini,q,true,5).map(x=>({title:x.title,ok:c?.gold.has(x.contentId)}))}
  }
  const output={
    corpus:{documents:documents.length,uniqueContentIds:new Set(benchDocs.map(d=>d.contentId)).size,indexJsonBytes:fs.statSync(path.join(repo,'digests/search-index.json')).size,
      chineseTitleDocs:benchDocs.filter(d=>/\p{Script=Han}/u.test(d.title)).length,nonemptyEntities:documents.filter(d=>d.entities?.length).length,nonemptyAliases:documents.filter(d=>d.aliases?.length).length},
    versions:{flexsearch:'0.8.212',minisearch:'7.2.0',node:process.version},
    testSet:{total:cases.length,byGroup:Object.fromEntries([...new Set(cases.map(c=>c.group))].map(g=>[g,cases.filter(c=>c.group===g).length])),exactTitles:cases.filter(c=>c.group==='exact-title').map(c=>c.query)},
    build:{flexMs:buildTimes.flex,miniMs:buildTimes.mini,flexMedianMs:percentile(buildTimes.flex,.5),miniMedianMs:percentile(buildTimes.mini,.5)},
    query:{flex:queryTiming(flexSearch,flex),mini:queryTiming(miniSearch,mini)},
    metrics:{flex:flexEval.groups,mini:miniEval.groups},
    serialized:{flex:await flexSerialized(flex),mini:miniSerialized(mini)},
    bundles:bundleStats(),rawSpecial,audited,
  }
  fs.writeFileSync('/tmp/search-bakeoff-results.json',JSON.stringify(output,null,2))
  console.log(JSON.stringify(output,null,2))
})().catch(e=>{console.error(e);process.exit(1)})
