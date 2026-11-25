'use strict';

const DAY = 86_400_000;
const jobFields = [
  'title', 'company', 'location', 'seniority', 'specialization', 'employment_type', 'remote',
  'salary_min', 'salary_max', 'salary_currency', 'salary_period', 'required_skills',
  'nice_to_have_skills', 'min_experience_years', 'education', 'company_headcount'
];
const listFields = ['required_skills', 'nice_to_have_skills'];
const filterFields = ['specialization', 'seniority', 'location', 'site', 'company_size'];
const normalized = value => String(value ?? '').normalize('NFKC').toLowerCase()
  .replace(/[^\p{L}\p{N}+#]+/gu, ' ').trim();
const normalizedSkill = value => String(value ?? '').normalize('NFKC').toLowerCase().replace(/\s+/g, ' ').trim();

function originalUrl(value) {
  try {
    const url = new URL(value);
    if (['http:', 'https:'].includes(url.protocol) && !url.username && !url.password) return url;
  } catch { /* Missing or malformed source URL. */ }
  return null;
}

function canonicalUrl(value) {
  const url = originalUrl(value);
  if (!url) return null;
  url.hash = '';
  for (const key of [...url.searchParams.keys()]) {
    if (/^(utm_.+|gclid|fbclid|trk)$/i.test(key)) url.searchParams.delete(key);
  }
  url.searchParams.sort();
  url.pathname = url.pathname.replace(/\/+$/, '') || '/';
  return url.href;
}

function sourceKey(job) {
  if (job.site && job.id != null && job.id !== '') return String(job.site) + ':' + job.id;
  return canonicalUrl(job.source_url);
}

function companySize(headcount) {
  if (!Number.isInteger(headcount) || headcount < 1) return 'unknown';
  if (headcount < 50) return 'small';
  if (headcount < 250) return 'medium';
  return 'large';
}

function timestamp(value) {
  const time = Date.parse(value);
  return Number.isFinite(time) ? time : null;
}

function comparable(field, value) {
  if (listFields.includes(field)) {
    return [...new Set((Array.isArray(value) ? value : []).map(normalizedSkill).filter(Boolean))].sort();
  }
  return typeof value === 'string' ? value.trim().replace(/\s+/g, ' ') : value ?? null;
}

function changedFields(before, after) {
  return jobFields.filter(field =>
    JSON.stringify(comparable(field, before[field])) !== JSON.stringify(comparable(field, after[field]))
  );
}

function titleSimilarity(a, b) {
  if (a === b) return 1;
  let row = Array.from({length: b.length + 1}, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const next = [i];
    for (let j = 1; j <= b.length; j++) {
      next[j] = Math.min(row[j] + 1, next[j - 1] + 1, row[j - 1] + Number(a[i - 1] !== b[j - 1]));
    }
    row = next;
  }
  return 1 - row[b.length] / Math.max(a.length, b.length);
}

function duplicateScore(a, b) {
  const url = canonicalUrl(a.source_url);
  if (url && url === canonicalUrl(b.source_url)) return 3;
  const title = normalized(a.title);
  const other = normalized(b.title);
  if (!title || !other) return 0;
  if (a.text_hash && a.text_hash === b.text_hash) return 3;
  if (!normalized(a.company) || normalized(a.company) !== normalized(b.company)) return 0;
  const location = normalized(a.location);
  if (location !== normalized(b.location) || (!location && !(a.remote && b.remote))) return 0;
  const days = Math.abs((timestamp(a.published_at) ?? a.firstSeen) - (timestamp(b.published_at) ?? b.firstSeen)) / DAY;
  if (days > 30 || !Number.isFinite(days)) return 0;
  const similarity = titleSimilarity(title, other);
  if (similarity < 0.84) return 0;
  const conflicting = ['seniority', 'specialization', 'employment_type'].some(field =>
    a[field] && b[field] && normalized(a[field]) !== normalized(b[field])
  );
  return similarity >= 0.9 && !conflicting ? 2 : 1;
}

function canonicalJobs(records) {
  const groups = [];
  const candidates = new Map();
  const ordered = [...records].sort((a, b) => a.firstSeen - b.firstSeen || a.key.localeCompare(b.key));
  const flag = (a, b) => {
    if (!candidates.has(a)) candidates.set(a, new Set());
    candidates.get(a).add(b);
  };
  for (const record of ordered) {
    const matches = groups.map(group => [group, Math.max(...group.map(member => duplicateScore(member, record)))])
      .filter(([, score]) => score > 0);
    const exact = matches.filter(([, score]) => score === 3);
    const strong = matches.filter(([, score]) => score === 2);
    const target = exact[0]?.[0] ?? (strong.length === 1 ? strong[0][0] : null);
    for (const [group] of matches) {
      if (group !== target) {
        flag(group[0].key, record.key);
        flag(record.key, group[0].key);
      }
    }
    if (target) target.push(record);
    else groups.push([record]);
  }

  const owners = new Map(groups.flatMap(group => group.map(member => [member.key, group[0].key])));
  return groups.map(group => {
    const first = group[0];
    const best = [...group].sort((a, b) =>
      b.versionAt - a.versionAt || (timestamp(b.parsed_at) ?? 0) - (timestamp(a.parsed_at) ?? 0)
    )[0];
    const possible = new Set(group.flatMap(member =>
      [...(candidates.get(member.key) ?? [])].map(key => owners.get(key))
    ));
    return {
      ...best,
      key: first.key,
      firstSeen: first.firstSeen,
      lastSeen: Math.max(...group.map(member => member.lastSeen)),
      sources: group,
      possibleDuplicates: [...possible].filter(key => key && key !== first.key)
    };
  }).sort((a, b) => b.versionAt - a.versionAt || b.firstSeen - a.firstSeen);
}

function snapshotRows(data, demo) {
  const rows = new Map();
  for (const job of data.jobs) {
    const key = sourceKey(job);
    if (!job.title || !key) continue;
    const previous = rows.get(key);
    if (previous && (timestamp(previous.parsed_at) ?? 0) > (timestamp(job.parsed_at) ?? 0)) continue;
    const headcount = job.company_headcount ?? demo?.company_headcounts?.[job.company];
    rows.set(key, {
      ...job, key, company_headcount: Number.isInteger(headcount) && headcount > 0 ? headcount : null,
      company_size: companySize(headcount)
    });
  }
  return rows;
}

function demoVersions(job, demo, anchor) {
  const versions = demo?.versions?.[job.key];
  if (versions?.length) {
    return versions.map(({days_ago, ...values}, index) => {
      const at = anchor - days_ago * DAY;
      const firstSeen = anchor - versions[0].days_ago * DAY;
      const version = {...job, ...values, firstSeen, versionAt: at, lastSeen: at};
      return {at, key: job.key, job: version, type: index ? 'updated' : 'added'};
    });
  }
  // Spread synthetic arrivals over the demo period. Use the same offset across reloads.
  let offset = 0;
  for (const character of job.key) offset = (offset * 31 + character.codePointAt(0)) % 28;
  const at = anchor - offset * DAY;
  return [{at, key: job.key, job: {...job, firstSeen: at, versionAt: at, lastSeen: at}, type: 'added'}];
}

function reconcileSnapshot(data, previous, demo, checkedAt = Date.now()) {
  const rows = snapshotRows(data, demo);
  const prior = previous?.current ?? {};
  const history = [...(previous?.history ?? [])];
  const current = Object.create(null);
  const known = new Map(history.filter(event => event.job).map(event => [event.key, event.job]));
  const snapshotAt = timestamp(data.generated_at);
  const anchor = previous?.anchor ?? snapshotAt ?? checkedAt;
  for (const [key, row] of rows) {
    const old = Object.hasOwn(prior, key) ? prior[key] : null;
    if (!old && !previous && demo) {
      const versions = demoVersions(row, demo, anchor);
      const last = versions.at(-1).job;
      history.push(...versions);
      current[key] = {...last, lastSeen: checkedAt};
      if (changedFields(last, row).length) {
        current[key] = {...last, ...row, lastSeen: checkedAt, versionAt: checkedAt};
        history.push({at: checkedAt, key, job: current[key], type: 'updated'});
      }
      continue;
    }
    const changed = !old || changedFields(old, row).length > 0;
    const firstSeen = old?.firstSeen ?? known.get(key)?.firstSeen ?? checkedAt;
    const versionAt = changed ? checkedAt : old.versionAt;
    current[key] = {...row, firstSeen, versionAt, lastSeen: checkedAt};
    if (changed) history.push({at: checkedAt, key, job: current[key], type: old ? 'updated' : 'added'});
  }
  for (const key of Object.keys(prior)) {
    if (!rows.has(key)) history.push({at: checkedAt, key, job: null, type: 'removed'});
  }
  history.sort((a, b) => a.at - b.at);
  return {anchor, checkedAt, current, history};
}

function updates(history) {
  const prior = new Map();
  const latest = new Map();
  for (const event of history) {
    const before = prior.get(event.key);
    if (event.type === 'updated' && before && event.job) {
      const fields = changedFields(before, event.job);
      if (fields.length) latest.set(event.key, {...event, before, fields});
    }
    if (event.job) prior.set(event.key, event.job);
    else prior.delete(event.key);
  }
  return [...latest.values()].sort((a, b) => b.at - a.at);
}

function payPoint(job) {
  return Number.isFinite(job.salary_min) && job.salary_min > 0 && job.salary_currency
    ? {amount: job.salary_min, currency: job.salary_currency, period: job.salary_period || 'month'}
    : null;
}

function salaryHistory(history, job) {
  // Follow the displayed source so syndicated copies don't create artificial price changes.
  const preferred = job.sources?.find(source => source.source_url === job.source_url);
  const key = preferred?.key ?? job.key;
  const points = [];
  let previous;
  for (const event of history) {
    if (event.key !== key) continue;
    const pay = event.job ? payPoint(event.job) : null;
    const comparablePay = pay ? {...pay, max: event.job.salary_max ?? null} : null;
    if (JSON.stringify(comparablePay) !== JSON.stringify(previous)) {
      points.push({at: event.at, pay: comparablePay, job: event.job});
    }
    previous = comparablePay;
  }
  return points;
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (!sorted.length) return null;
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function salaryComparisons(jobs) {
  const units = new Map();
  for (const job of jobs) {
    const pay = payPoint(job);
    if (!pay || job.company_size === 'unknown') continue;
    const key = pay.currency + '/' + pay.period;
    if (!units.has(key)) units.set(key, {currency: pay.currency, period: pay.period, groups: new Map()});
    const {groups} = units.get(key);
    if (!groups.has(job.company_size)) groups.set(job.company_size, []);
    groups.get(job.company_size).push(pay.amount);
  }
  return [...units.values()].map(unit => {
    const baseline = ['small', 'medium', 'large'].find(size => unit.groups.has(size));
    const reference = median(unit.groups.get(baseline));
    const rows = ['small', 'medium', 'large'].map(size => {
      const values = unit.groups.get(size) ?? [];
      const amount = median(values);
      return {size, count: values.length, amount, delta: amount == null ? null : (amount / reference - 1) * 100};
    });
    return {...unit, baseline, rows};
  }).sort((a, b) => Number(b.currency === 'EUR') - Number(a.currency === 'EUR') || a.currency.localeCompare(b.currency));
}

function countHistory(state, start, end, step, matches) {
  const points = [];
  const active = new Map();
  let index = 0;
  for (let begin = start; begin < end; begin += step) {
    const until = Math.min(begin + step, end);
    const bucket = [];
    while (index < state.history.length && state.history[index].at < until) {
      const event = state.history[index++];
      if (event.job) active.set(event.key, event.job);
      else active.delete(event.key);
      if (event.at >= begin) bucket.push(event);
    }
    const jobs = canonicalJobs(active.values()).filter(matches);
    const bySource = new Map(jobs.flatMap(job => job.sources.map(source => [source.key, job])));
    const added = new Set();
    const updated = new Set();
    for (const event of bucket) {
      const job = bySource.get(event.key);
      if (!job) continue;
      if (event.type === 'added' && job.firstSeen >= begin) added.add(job.key);
      if (event.type === 'updated') updated.add(job.key);
    }
    points.push({at: begin, until, jobs, active: jobs.length, added: added.size, updated: updated.size});
  }
  return points;
}
