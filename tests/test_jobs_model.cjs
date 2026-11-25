const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {runInNewContext} = require('node:vm');

const frontend = join(__dirname, '..', 'frontend');
const model = readFileSync(join(frontend, 'jobs-model.js'), 'utf8');
const load = filename => JSON.parse(readFileSync(join(frontend, 'data', filename), 'utf8'));
const evaluate = (code, input = {}) => JSON.parse(JSON.stringify(runInNewContext(
  model + '\n' + code, {URL, ...input}
)));

test('demo history shows three edited jobs and records salary changes across reloads', () => {
  const data = load('jobs.json');
  const demo = load('demo.json');
  const result = evaluate(`{
    const now = Date.parse(data.generated_at) + 3 * DAY;
    const first = reconcileSnapshot(data, null, demo, now);
    const newer = {...data, jobs: data.jobs.map(job =>
      job.id === '4009826165' ? {...job, salary_min: 4100} : job
    )};
    const updated = reconcileSnapshot(newer, first, demo, now + DAY);
    const same = reconcileSnapshot(newer, updated, demo, now + DAY * 2);
    const example = same.current['linkedin:4009826165'];
    ({
      initial: updates(first.history).length,
      updates: updates(same.history).length,
      latest: updates(same.history)[0].job.salary_min,
      history: salaryHistory(same.history, example).map(point => point.pay.amount),
      duplicateEvents: same.history.length - updated.history.length,
      size: example.company_size
    });
  }`, {data, demo});
  assert.deepEqual(result, {
    initial: 3, updates: 3, latest: 4100, history: [3100, 3400, 3800, 4100], duplicateEvents: 0, size: 'small'
  });
});

test('syndicated offers count once, while conflicting seniority goes to review', () => {
  const result = evaluate(`{
    const time = Date.parse('2026-11-01');
    const base = {title: 'Backend Software Developer', company: 'Example', location: 'Žilina', seniority: 'senior',
      firstSeen: time, versionAt: time, lastSeen: time};
    const rows = [
      {...base, key: 'one', site: 'site1', source_url: 'https://example.com/jobs/1?utm_campaign=demo'},
      {...base, key: 'two', site: 'site2', title: 'Backend Software Developers', source_url: 'https://example.net/jobs/2'},
      {...base, key: 'three', site: 'site1', seniority: 'junior', source_url: 'https://example.com/jobs/3'},
      {...base, key: 'four', site: 'site2', title: 'Other', source_url: 'https://example.com/jobs/1#source'}
    ];
    canonicalJobs(rows).map(job => [job.key, job.sources.length, job.possibleDuplicates.length]);
  }`);
  assert.deepEqual(result, [['four', 3, 1], ['three', 1, 1]]);
});

test('trends use historical availability and pay comparisons keep currency and period separate', () => {
  const result = evaluate(`{
    const date = Date.parse('2026-11-01');
    const first = {title: 'QA', site: 'demo', id: 1, company: 'One', salary_min: 2000,
      salary_currency: 'EUR', company_headcount: 22};
    const second = {...first, id: 2, company: 'Two', salary_min: 2400, company_headcount: 410};
    const otherUnit = {...second, id: 3, company: 'Three', salary_min: 15, salary_period: 'hour'};
    const snapshot = jobs => ({dataset_kind: 'synthetic', jobs});
    let state = reconcileSnapshot(snapshot([first]), null, null, date);
    state = reconcileSnapshot(snapshot([first, second, otherUnit]), state, null, date + DAY);
    state = reconcileSnapshot(snapshot([second, otherUnit]), state, null, date + 2 * DAY);
    const points = countHistory(state, date, date + 3 * DAY, DAY, () => true);
    const pay = salaryComparisons(points[1].jobs);
    ({
      counts: points.map(point => point.active),
      delta: Math.round(pay.find(unit => unit.period === 'month').rows.find(row => row.size === 'large').delta),
      samples: pay.map(unit => unit.rows.reduce((total, row) => total + row.count, 0))
    });
  }`);
  assert.deepEqual(result, {counts: [1, 3, 2], delta: 20, samples: [2, 1]});
});
