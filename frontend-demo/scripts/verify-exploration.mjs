import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';

const dir = await mkdtemp(join(tmpdir(), 'ahead-exploration-'));
try {
  for (const name of ['trends', 'search-data', 'world-data', 'trend-navigation', 'flight', 'country-interest']) {
    const source = await readFile(new URL(`../app/${name}.ts`, import.meta.url), 'utf8');
    const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
    await writeFile(join(dir, `${name}.mjs`), outputText.replaceAll("'./trends'", "'./trends.mjs'").replaceAll("'./world-data'", "'./world-data.mjs'"));
  }
  const { allTrends, categories, getTrends } = await import(pathToFileURL(join(dir, 'trends.mjs')).href);
  const { searchTrends } = await import(pathToFileURL(join(dir, 'search-data.mjs')).href);
  const { countries, getSpreadStory, spreadAtDay, spreadCurve, dayLabel, LAST_DAY, projectPoint } = await import(pathToFileURL(join(dir, 'world-data.mjs')).href);
  const { searchHref, worldHref, worldSelection, validCategory } = await import(pathToFileURL(join(dir, 'trend-navigation.mjs')).href);
  const { advanceFlightClock, flightAtTime, flightPoint, DAY_DURATION_MS, END_HOLD_DAYS } = await import(pathToFileURL(join(dir, 'flight.mjs')).href);
  const { worldStats, interestPeriods } = await import(pathToFileURL(join(dir, 'country-interest.mjs')).href);
  const base = { query: '', scope: 'interests', interests: ['dev', 'fashion'], kind: 'all', sort: 'relevance', savedOnly: false, saved: [] };
  assert.equal(new Set(allTrends.map(t => t.id)).size, allTrends.length);
  assert.equal(searchTrends(base).length, 22);
  const find = query => searchTrends({ ...base, query });
  assert.equal(find('AI Agent')[0].name, 'AI Agent');
  assert.equal(find('ＡＩ ＡＧＥＮＴ')[0].name, 'AI Agent');
  assert.equal(find('ai-agent')[0].name, 'AI Agent');
  assert.ok(find('AI 에이전트').some(t => t.name === 'AI Agent'));
  assert.equal(find('발레 스니커즈')[0].name, 'Ballet Sneakers');
  assert.equal(find('no-such-trend-xyz').length, 0);
  assert.equal(searchTrends({ ...base, scope: 'interests' }).length, 22);
  assert.ok(searchTrends({ ...base, scope: 'fashion', kind: 'new' }).every(t => t.category === 'fashion' && t.kind === 'new'));
  assert.equal(searchTrends({ ...base, scope: 'fashion', kind: 'new' }).length, 3);
  const saved = ['dev-top-0', 'fashion-top-1'];
  assert.equal(searchTrends({ ...base, savedOnly: true, saved, scope: 'fashion' })[0].id, 'fashion-top-1');
  assert.equal(searchTrends({ ...base, savedOnly: true, saved: [] }).length, 0);
  for (const sort of ['mentions', 'growth']) {
    const sorted = searchTrends({ ...base, sort });
    assert.ok(sorted.every((t, i) => !i || sorted[i - 1][sort] >= t[sort]));
  }
  // Every cross-page URL must preserve category and the exact trend, including
  // new/rising records and categories outside the user's onboarding selection.
  for (const trend of allTrends) {
    const searchUrl = new URL(searchHref(trend), 'https://example.test');
    const scope = validCategory(searchUrl.searchParams.get('category'));
    const results = searchTrends({ ...base, query: searchUrl.searchParams.get('q'), scope });
    assert.ok(results.some(t => t.id === trend.id));
    const worldUrl = new URL(worldHref(trend), 'https://example.test');
    const selection = worldSelection(worldUrl.searchParams.get('trend'), 'dev');
    assert.equal(selection.trend.id, trend.id);
    assert.equal(selection.category.id, trend.category);
    assert.ok(selection.options.some(t => t.id === trend.id));
    assert.equal(new Set(selection.options.map(t => t.id)).size, selection.options.length);
  }
  assert.equal(validCategory('all'), undefined);
  assert.equal(validCategory(['dev']), undefined);
  assert.equal(worldSelection('invalid-id', 'fashion').category.id, 'fashion');
  // Short-period map rankings and chart endpoints must describe the same data.
  // All linked trends, including new/rising ones, must support both views.
  for (const trend of allTrends) {
    const periods = ['day', 'week'];
    for (const period of periods) {
      const stats = worldStats(trend, period);
      assert.equal(stats.length, countries.length);
      assert.equal(new Set(stats.map(c => c.id)).size, countries.length);
      assert.ok(stats.every((c, i) => !i || stats[i - 1].score >= c.score));
      for (const c of stats) {
        assert.equal(c.series.length, interestPeriods[period].axis.length);
        assert.ok(c.series.every(n => Number.isInteger(n) && n >= 0 && n <= 100));
        assert.equal(c.score, c.series.at(-1));
        assert.equal(c.change, c.score - c.series[0]);
      }
    }
    assert.notDeepEqual(worldStats(trend, 'day'), worldStats(trend, 'week'));
  }
  console.log('Passed: 1-day / 7-day country rankings, chart endpoints and period-specific data for all 99 trends.');
  let snapshots = 0;
  for (const category of categories) for (const trend of getTrends(category.id, 'top', 'month')) {
    const story = getSpreadStory(trend);
    assert.equal(story.observations.length, countries.length);
    assert.equal(new Set(story.observations.map(o => o.country.id)).size, countries.length);
    assert.equal(story.observations.filter(o => !o.parent).length, 1);
    const origin = story.observations[0];
    assert.equal(origin.parent, null);
    for (const o of story.observations) {
      assert.equal(o.dailyMentions.length, 30);
      assert.ok(o.firstDay >= 0 && o.firstDay <= LAST_DAY);
      assert.ok(o.dailyMentions.slice(0, o.firstDay).every(n => n === 0));
      assert.ok(o.dailyMentions.slice(o.firstDay).every(n => Number.isInteger(n) && n > 0));
      const p = projectPoint(o.country.lon, o.country.lat);
      assert.ok(p.x >= 0 && p.x <= 1000 && p.y >= 0 && p.y <= 460);
      if (o.parent) {
        const parent = story.observations.find(p => p.country.id === o.parent);
        assert.ok(parent && parent.firstDay < o.firstDay, 'No backward or cyclic transmission links');
        assert.ok(!spreadCurve(parent, o).includes('NaN'));
      }
    }
    let previousCount = 0;
    for (let day = 0; day <= LAST_DAY; day++) {
      const s = spreadAtDay(story, day);
      assert.ok(s.reached.length >= previousCount);
      assert.ok(s.reached.every(o => o.firstDay <= day), 'No future observations exposed');
      assert.ok(s.links.every(o => o.parent && s.reached.some(p => p.country.id === o.parent)));
      assert.ok(s.newlyReached.every(o => o.firstDay === day));
      assert.equal(s.mentions, s.reached.reduce((n, o) => n + o.dailyMentions[day], 0));
      for (const o of story.observations.filter(o => o.firstDay > 0)) {
        assert.ok(!spreadAtDay(story, o.firstDay - 1).reached.some(p => p.country.id === o.country.id));
        assert.ok(spreadAtDay(story, o.firstDay).reached.some(p => p.country.id === o.country.id));
      }
      previousCount = s.reached.length;
      snapshots++;
    }
    assert.equal(previousCount, countries.length);
    assert.deepEqual(spreadAtDay(story, LAST_DAY), spreadAtDay(story, 999));
    assert.deepEqual(spreadAtDay(story, 0), spreadAtDay(story, -1));
    assert.deepEqual(spreadAtDay(story, 0), spreadAtDay(story, Number.NaN));
    // Rewinding must reproduce exactly the earlier state, without future records.
    const early = spreadAtDay(story, 7);
    spreadAtDay(story, LAST_DAY);
    assert.deepEqual(early, spreadAtDay(story, 7));
  }
  assert.equal(dayLabel(0), '08.01');
  assert.equal(dayLabel(LAST_DAY), '08.30');
  // Flights must start immediately, stay on the route, and arrive before a
  // destination becomes a recorded observation. Check every selectable story.
  for (const trend of allTrends) {
    const story = getSpreadStory(trend);
    const origin = story.observations[0];
    assert.ok(flightAtTime(story, origin.firstDay), 'Autoplay begins without waiting');
    assert.equal(flightAtTime(story, origin.firstDay - .01), null);
    for (let i = 1; i < story.observations.length; i++) {
      const target = story.observations[i];
      const source = story.observations.find(o => o.country.id === target.parent);
      const start = Math.max(source.firstDay, story.observations[i - 1].firstDay);
      for (const fraction of [0, .25, .5, .75, .999]) {
        const time = start + (target.firstDay - start) * fraction;
        const flight = flightAtTime(story, time);
        assert.equal(flight.target.country.id, target.country.id);
        assert.equal(flight.source.country.id, source.country.id);
        assert.ok(Math.abs(flight.progress - fraction) < 1e-10);
        assert.ok([flight.x, flight.y, flight.angle].every(Number.isFinite));
        assert.ok(flight.x >= 0 && flight.x <= 1000 && flight.y >= 0 && flight.y <= 460);
        const reached = spreadAtDay(story, Math.floor(time)).reached;
        assert.ok(reached.some(o => o.country.id === source.country.id));
        assert.ok(!reached.some(o => o.country.id === target.country.id));
      }
      for (const [fraction, country] of [[0, source.country], [1, target.country]]) {
        const point = flightPoint(source, target, fraction);
        const expected = projectPoint(country.lon, country.lat);
        assert.equal(point.x, expected.x);
        assert.equal(point.y, expected.y);
      }
      assert.notEqual(flightAtTime(story, target.firstDay)?.target.country.id, target.country.id);
    }
    assert.equal(flightAtTime(story, LAST_DAY), null);
    assert.equal(advanceFlightClock(origin.firstDay, DAY_DURATION_MS, 1, origin.firstDay), origin.firstDay + 1);
    assert.equal(advanceFlightClock(origin.firstDay, DAY_DURATION_MS, 2, origin.firstDay), origin.firstDay + 2);
    assert.equal(advanceFlightClock(LAST_DAY, DAY_DURATION_MS, 1, origin.firstDay), LAST_DAY + 1);
    const restart = advanceFlightClock(LAST_DAY, DAY_DURATION_MS * END_HOLD_DAYS, 1, origin.firstDay);
    assert.equal(restart, origin.firstDay);
    assert.ok(flightAtTime(story, restart), 'Repeated playback starts with a flight');
  }
  console.log('Passed: continuous flight timing, path geometry, arrivals, playback speed and looping across all 99 trends.');
  console.log(`Passed: search normalization, Korean aliases, combined filters, saved-only, empty states, sorting; 99 cross-page trend links; ${snapshots} spread snapshots, chronology, parent links, date boundaries and rewind.`);
} finally {
  await rm(dir, { recursive: true, force: true });
}
