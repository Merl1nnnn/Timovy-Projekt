'use strict';

const SkillAnalytics = (() => {
  const clean = value => typeof value === 'string' ? value.normalize('NFKC').trim().replace(/\s+/g, ' ') : '';
  const keyOf = value => clean(value).toLowerCase();
  const byCount = (a, b) => b.count - a.count || a.name.localeCompare(b.name, 'en');

  function eligibleJobs(jobs) {
    return jobs.filter(job => job.low_confidence === false && job.review_required !== true &&
      (job.validation_status == null || job.validation_status === 'validated'));
  }

  function skillsOf(job) {
    const skills = new Map();
    for (const field of ['required_skills', 'nice_to_have_skills']) {
      for (const value of Array.isArray(job[field]) ? job[field] : []) {
        const name = clean(value);
        if (name && !skills.has(keyOf(name))) skills.set(keyOf(name), name);
      }
    }
    return [...skills.values()];
  }

  function catalog(jobs) {
    const skills = new Map();
    for (const job of jobs) {
      for (const name of skillsOf(job)) {
        const key = keyOf(name);
        if (!skills.has(key)) skills.set(key, {name, key, count: 0});
        skills.get(key).count++;
      }
    }
    return [...skills.values()].sort(byCount);
  }

  function matchingJobs(jobs, selectedKeys) {
    const selected = [...new Set(Array.from(selectedKeys || [], keyOf).filter(Boolean))];
    return jobs.filter(job => {
      const keys = new Set(skillsOf(job).map(keyOf));
      return selected.every(key => keys.has(key));
    });
  }

  const rolePatterns = [
    ['Backend', /\bback[ -]?end\b/i],
    ['Frontend', /\bfront[ -]?end\b/i],
    ['ML', /\b(?:machine learning|ml)\b/i],
    ['DevOps', /\b(?:devops|sre|site reliability)\b/i],
    ['Data', /\bdata (?:engineer|engineering|scientist|science|analyst|analytics)\b/i],
    ['QA', /\b(?:qa|quality assurance|test automation|software test(?:er|ing))\b/i],
    ['Security', /\b(?:cyber[ -]?security|security)\b/i],
    ['Mobile', /\b(?:mobile|android|ios)\b/i],
    ['Fullstack', /\bfull[ -]?stack\b/i]
  ];

  function canonicalRole(value) {
    const roleKey = keyOf(value).replace(/[ -]/g, '');
    if (roleKey === 'sre') return 'DevOps';
    if (roleKey === 'machinelearning') return 'ML';
    return rolePatterns.find(([name]) => keyOf(name) === roleKey)?.[0] || null;
  }

  function rolesOf(job) {
    const explicit = (Array.isArray(job.role_specializations) ? job.role_specializations : [])
      .map(canonicalRole).filter(Boolean);
    if (explicit.length) return [...new Set(explicit)];
    const roles = new Set([canonicalRole(job.specialization)].filter(Boolean));
    const title = clean(job.title);
    for (const [name, pattern] of rolePatterns) if (pattern.test(title)) roles.add(name);
    return [...roles];
  }

  function roleOptions(jobs) {
    const roles = new Map();
    for (const job of jobs) {
      for (const name of rolesOf(job)) {
        const key = keyOf(name);
        if (!roles.has(key)) roles.set(key, {key, name, count: 0});
        roles.get(key).count++;
      }
    }
    return [...roles.values()].sort(byCount);
  }

  function filterProfile(jobs, profile = {}) {
    const role = keyOf(profile.role);
    const seniority = keyOf(profile.seniority);
    const location = keyOf(profile.location);
    return matchingJobs(jobs, profile.skills).filter(job =>
      (!role || rolesOf(job).some(value => keyOf(value) === role)) &&
      (!seniority || keyOf(job.seniority) === seniority) &&
      (!location || keyOf(job.location) === location));
  }

  function funnel(jobs, selectedKeys) {
    const total = jobs.length;
    const names = new Map(catalog(jobs).map(skill => [skill.key, skill.name]));
    const selected = new Map();
    for (const value of selectedKeys || []) {
      const key = keyOf(value);
      if (key && !selected.has(key)) selected.set(key, clean(value));
    }
    const result = [{key: null, name: null, before: total, count: total, removed: 0,
      remainingShare: total ? 1 : null, retention: total ? 1 : null}];
    let remaining = jobs;
    for (const [key, fallback] of selected) {
      const before = remaining.length;
      remaining = matchingJobs(remaining, [key]);
      const count = remaining.length;
      result.push({key, name: names.get(key) || fallback, before, count, removed: before - count,
        remainingShare: total ? count / total : null, retention: before ? count / before : null});
    }
    return result;
  }

  function histogram(jobs, field) {
    const groups = new Map();
    for (const job of jobs) {
      const name = clean(job[field]) || 'unknown';
      const key = keyOf(name);
      if (!groups.has(key)) groups.set(key, {name, count: 0});
      groups.get(key).count++;
    }
    return [...groups.values()].sort(byCount);
  }

  function quantile(sorted, fraction) {
    const position = (sorted.length - 1) * fraction;
    const lower = Math.floor(position);
    const upper = Math.ceil(position);
    return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower);
  }

  function salaryObservation(job, options) {
    const amount = job.salary_min;
    const currency = clean(job.salary_currency).toUpperCase();
    const period = keyOf(job.salary_period == null ? 'month' : job.salary_period);
    if (keyOf(job.salary_basis) === 'net' || typeof amount !== 'number' || !Number.isFinite(amount) || amount <= 0 ||
        !currency || !['hour', 'month', 'year'].includes(period)) return null;
    if (options == null) return {value: amount, currency, period, derived: false};
    const targetCurrency = clean(options.currency).toUpperCase();
    const targetPeriod = keyOf(options.period);
    if (!targetCurrency || !['hour', 'month', 'year'].includes(targetPeriod)) return null;
    let value = amount;
    if (currency !== targetCurrency) {
      const rate = code => code === 'EUR' ? 1 : options.rates?.[code];
      const sourceRate = rate(currency);
      const targetRate = rate(targetCurrency);
      if (typeof sourceRate !== 'number' || !Number.isFinite(sourceRate) || sourceRate <= 0 ||
          typeof targetRate !== 'number' || !Number.isFinite(targetRate) || targetRate <= 0) return null;
      value = value / sourceRate * targetRate;
    }
    if (period !== targetPeriod) {
      let annualHours;
      if (period === 'hour' || targetPeriod === 'hour') {
        const employment = keyOf(job.employment_type).replace(/[ -]+/g, '_');
        const weeklyHours = employment === 'part_time' ? 20 : employment === 'full_time' ? 40 : null;
        if (weeklyHours === null) return null;
        annualHours = weeklyHours * 52;
      }
      const annual = period === 'year' ? value : period === 'month' ? value * 12 : value * annualHours;
      value = targetPeriod === 'year' ? annual : targetPeriod === 'month' ? annual / 12 : annual / annualHours;
    }
    return Number.isFinite(value) && value > 0
      ? {value, currency: targetCurrency, period: targetPeriod, derived: currency !== targetCurrency || period !== targetPeriod}
      : null;
  }

  function convertedSalary(job, options) { return options ? salaryObservation(job, options)?.value ?? null : null; }

  function conversionCoverage(jobs, options) {
    const converted = jobs.map(job => salaryObservation(job, options)).filter(Boolean);
    return {count: converted.length, derivedCount: converted.filter(value => value.derived).length,
      excludedCount: jobs.length - converted.length};
  }

  function salaryGroups(jobs, options) {
    const groups = new Map();
    for (const job of jobs) {
      const observation = salaryObservation(job, options);
      if (!observation) continue;
      const {value: amount, currency, period, derived} = observation;
      const key = `${currency}:${period}`;
      if (!groups.has(key)) groups.set(key, {currency, period, values: [], ...(options == null ? {} : {derivedCount: 0})});
      groups.get(key).values.push(amount);
      if (options != null && derived) groups.get(key).derivedCount++;
    }
    return [...groups.values()].map(group => {
      const values = group.values.sort((a, b) => a - b);
      return {...group, ...(options == null ? {} : {excludedCount: jobs.length - values.length}), count: values.length, median: quantile(values, 0.5),
        p25: quantile(values, 0.25), p75: quantile(values, 0.75), min: values[0], max: values.at(-1)};
    }).sort((a, b) => b.count - a.count || a.currency.localeCompare(b.currency, 'en') || a.period.localeCompare(b.period, 'en'));
  }

  function summarize(jobs, options) {
    return {
      count: jobs.length,
      companies: new Set(jobs.map(job => keyOf(job.company)).filter(Boolean)).size,
      remoteCount: jobs.filter(job => job.remote === true).length,
      seniority: histogram(jobs, 'seniority'),
      locations: histogram(jobs, 'location'),
      skills: catalog(jobs),
      salaryGroups: salaryGroups(jobs, options)
    };
  }

  function salaryFor(jobs, unit = {}) {
    const currency = clean(unit.currency).toUpperCase();
    const period = keyOf(unit.period);
    if (!currency || !['hour', 'month', 'year'].includes(period)) return null;
    return salaryGroups(jobs, unit.convert === true ? unit : undefined)
      .find(group => group.currency === currency && group.period === period) || null;
  }

  function compareOffer(jobs, profile = {}, offer = {}) {
    const matched = filterProfile(jobs, profile);
    const summary = summarize(matched);
    const salary = salaryFor(matched, offer);
    const offerAmount = typeof offer.amount === 'number' && Number.isFinite(offer.amount) ? offer.amount : null;
    const validOffer = offerAmount !== null && offerAmount > 0 && Boolean(clean(offer.currency)) &&
      ['hour', 'month', 'year'].includes(keyOf(offer.period));
    const result = {
      count: summary.count, companies: summary.companies, remoteCount: summary.remoteCount,
      salaryCount: salary?.count || 0, median: salary?.median ?? null, p25: salary?.p25 ?? null,
      p75: salary?.p75 ?? null, min: salary?.min ?? null, max: salary?.max ?? null,
      offerAmount, validOffer, percentile: null, below: null, equal: null, above: null,
      differencePercent: null, status: validOffer ? 'no_salary' : 'invalid'
    };
    if (offer.convert === true) Object.assign(result, {salaryDerivedCount: salary?.derivedCount || 0,
      salaryExcludedCount: matched.length - (salary?.count || 0)});
    if (!validOffer || !salary) return result;
    const compare = (a, b) => Math.abs(a - b) <= Number.EPSILON * Math.max(1, a, b) * 8 ? 0 : Math.sign(a - b);
    result.below = salary.values.filter(value => compare(value, offerAmount) < 0).length;
    result.equal = salary.values.filter(value => compare(value, offerAmount) === 0).length;
    result.above = salary.count - result.below - result.equal;
    // Midrank percentile among compatible advertised minima: ties contribute half their count.
    result.percentile = (result.below + 0.5 * result.equal) / salary.count * 100;
    result.differencePercent = compare(offerAmount, salary.median) === 0 ? 0 : (offerAmount - salary.median) / salary.median * 100;
    result.status = compare(offerAmount, salary.p25) < 0 ? 'below_range' : compare(offerAmount, salary.p75) > 0 ? 'above_range' : 'within_range';
    return result;
  }

  function compareProfiles(jobs, a = {}, b = {}, unit = {}) {
    const first = filterProfile(jobs, a);
    const second = filterProfile(jobs, b);
    const firstSet = new Set(first);
    const describe = selected => ({...summarize(selected, unit.convert === true ? unit : undefined), share: jobs.length ? selected.length / jobs.length : null,
      salary: salaryFor(selected, unit)});
    const result = {a: describe(first), b: describe(second),
      overlap: second.filter(job => firstSet.has(job)).length, medianDifferencePercent: null};
    if (result.a.salary && result.b.salary) {
      result.medianDifferencePercent = (result.b.salary.median - result.a.salary.median) / result.a.salary.median * 100;
    }
    return result;
  }

  function validDay(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}(?:$|T)/.test(value)) return null;
    const day = value.slice(0, 10);
    const dayTime = Date.parse(`${day}T00:00:00Z`);
    if (!Number.isFinite(dayTime) || new Date(dayTime).toISOString().slice(0, 10) !== day) return null;
    if (value.length === 10) return day;
    // Time-zone-less timestamps are interpreted as UTC, never the viewer's local zone.
    const timestamp = Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`);
    return Number.isFinite(timestamp) ? new Date(timestamp).toISOString().slice(0, 10) : null;
  }

  function observationDate(job) {
    for (const [field, kind] of [['published_at', 'published'], ['scraped_at', 'scraped'], ['parsed_at', 'parsed']]) {
      const date = validDay(job[field]);
      if (date) return {date, kind};
    }
    return {date: null, kind: 'missing'};
  }

  function dateOf(job) { return observationDate(job).date; }
  function dateKind(job) { return observationDate(job).kind; }

  function trend(jobs, options) {
    const dates = new Map();
    for (const job of jobs) {
      const {date, kind} = observationDate(job);
      if (!date) continue;
      if (!dates.has(date)) dates.set(date, {jobs: [], dateKinds: {published: 0, scraped: 0, parsed: 0}});
      dates.get(date).jobs.push(job);
      dates.get(date).dateKinds[kind]++;
    }
    return [...dates].sort(([a], [b]) => a.localeCompare(b)).map(([date, bucket]) => ({
      date, count: bucket.jobs.length, salaryGroups: salaryGroups(bucket.jobs, options), dateKinds: bucket.dateKinds
    }));
  }

  return {eligibleJobs, skillsOf, catalog, matchingJobs, rolesOf, roleOptions, filterProfile, funnel,
    compareOffer, compareProfiles, convertedSalary, conversionCoverage, salaryGroups, summarize, dateOf, dateKind, trend};
})();
