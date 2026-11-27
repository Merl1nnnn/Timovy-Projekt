const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {runInNewContext} = require('node:vm');

const model = readFileSync(join(__dirname, '..', 'frontend', 'analytics-model.js'), 'utf8');
const evaluate = (code, input = {}) => JSON.parse(JSON.stringify(runInNewContext(model + '\n' + code, input)));

test('only explicitly verified postings enter analytics', () => {
  const jobs = [
    {id: 1, low_confidence: false},
    {id: 2, low_confidence: false, validation_status: 'validated'},
    {id: 3, low_confidence: true},
    {id: 4},
    {id: 5, low_confidence: false, review_required: true},
    {id: 6, low_confidence: false, validation_status: 'review'},
    {id: 7, low_confidence: false, validation_status: 'unvalidated'}
  ];
  assert.deepEqual(evaluate('SkillAnalytics.eligibleJobs(jobs).map(job => job.id)', {jobs}), [1, 2]);
});

test('skill catalog counts each posting once and AND filtering crosses both lists', () => {
  const jobs = [
    {id: 1, required_skills: [' Python ', 'PYTHON', 'Django'], nice_to_have_skills: ['python', ' Docker ']},
    {id: 2, required_skills: ['python'], nice_to_have_skills: ['ML']},
    {id: 3, required_skills: ['Docker'], nice_to_have_skills: []},
    {id: 4, required_skills: [null, 42, '  ']}
  ];
  assert.deepEqual(evaluate('SkillAnalytics.catalog(jobs)', {jobs}), [
    {name: 'Docker', key: 'docker', count: 2}, {name: 'Python', key: 'python', count: 2},
    {name: 'Django', key: 'django', count: 1}, {name: 'ML', key: 'ml', count: 1}
  ]);
  assert.deepEqual(evaluate("SkillAnalytics.matchingJobs(jobs, [' PYTHON ', 'docker']).map(job => job.id)", {jobs}), [1]);
  assert.deepEqual(evaluate("SkillAnalytics.matchingJobs(jobs, ['python', 'PYTHON']).map(job => job.id)", {jobs}), [1, 2]);
  assert.equal(evaluate('SkillAnalytics.matchingJobs(jobs, []).length', {jobs}), 4);
  assert.deepEqual(evaluate("SkillAnalytics.matchingJobs(jobs, ['missing'])", {jobs}), []);
});

test('salary medians use positive lower bounds without mixing currencies or units', () => {
  const jobs = [1000, 2000, 3000, 4000].map(salary_min => ({salary_min, salary_currency: 'eur'}));
  jobs.push(
    {salary_min: 20, salary_currency: 'EUR', salary_period: 'hour'},
    {salary_min: 50000, salary_currency: 'EUR', salary_period: 'year'},
    {salary_min: 3000, salary_currency: 'USD', salary_period: 'month'},
    {salary_max: 5000, salary_currency: 'EUR'},
    {salary_min: '8000', salary_currency: 'EUR'},
    {salary_min: -100, salary_currency: 'EUR'},
    {salary_min: Infinity, salary_currency: 'EUR'},
    {salary_min: 0, salary_currency: 'EUR'},
    {salary_min: 6000, salary_currency: 'EUR', salary_period: 'week'},
    {salary_min: 6000}
  );
  const groups = evaluate('SkillAnalytics.summarize(jobs).salaryGroups', {jobs});
  assert.equal(groups.length, 4);
  assert.deepEqual(groups[0], {
    currency: 'EUR', period: 'month', values: [1000, 2000, 3000, 4000], count: 4,
    median: 2500, p25: 1750, p75: 3250, min: 1000, max: 4000
  });
  const hourly = groups.find(group => group.period === 'hour');
  assert.equal(hourly.median, 20);
  assert.equal(hourly.p25, 20);
  assert.equal(hourly.p75, 20);
});

test('summary excludes missing companies and reports unknown histogram categories', () => {
  const jobs = [
    {company: ' ACME ', seniority: 'Senior', location: 'Bratislava', remote: true},
    {company: 'acme', seniority: 'senior', location: 'Bratislava', remote: false},
    {company: 'Other', seniority: 'Junior', location: 'Košice', remote: 'true'},
    {}
  ];
  const result = evaluate('SkillAnalytics.summarize(jobs)', {jobs});
  assert.equal(result.count, 4);
  assert.equal(result.companies, 2);
  assert.equal(result.remoteCount, 1);
  assert.deepEqual(result.seniority, [{name: 'Senior', count: 2}, {name: 'Junior', count: 1}, {name: 'unknown', count: 1}]);
  assert.equal(result.locations[0].count, 2);
  assert.deepEqual(result.salaryGroups, []);
});

test('dates prefer publication, fall back to collection or parse date and never invent dates', () => {
  const jobs = [
    {published_at: '2026-11-10', scraped_at: '2026-11-12T10:00:00Z'},
    {published_at: '2026-02-30', scraped_at: '2026-11-12T23:30:00-02:00'},
    {scraped_at: 'invalid', parsed_at: '2026-11-14T12:34:56'},
    {published_at: '2026-13-01', parsed_at: null},
    {published_at: 1234}
  ];
  assert.deepEqual(evaluate('jobs.map(job => [SkillAnalytics.dateOf(job), SkillAnalytics.dateKind(job)])', {jobs}), [
    ['2026-11-10', 'published'], ['2026-11-13', 'scraped'], ['2026-11-14', 'parsed'], [null, 'missing'], [null, 'missing']
  ]);
  const points = evaluate('SkillAnalytics.trend(jobs)', {jobs});
  assert.deepEqual(points.map(point => [point.date, point.count]), [['2026-11-10', 1], ['2026-11-13', 1], ['2026-11-14', 1]]);
  assert.deepEqual(points[1].dateKinds, {published: 0, scraped: 1, parsed: 0});
});

test('trend groups daily salary observations and empty selections stay empty', () => {
  const jobs = [
    {parsed_at: '2026-11-10T10:00:00Z', salary_min: 1000, salary_currency: 'EUR'},
    {parsed_at: '2026-11-10T16:00:00Z', salary_min: 3000, salary_currency: 'EUR'},
    {salary_min: 9000, salary_currency: 'EUR'}
  ];
  const points = evaluate('SkillAnalytics.trend(jobs)', {jobs});
  assert.equal(points.length, 1);
  assert.equal(points[0].count, 2);
  assert.equal(points[0].salaryGroups[0].median, 2000);
  assert.deepEqual(evaluate('SkillAnalytics.trend([])'), []);
  assert.equal(evaluate('SkillAnalytics.summarize([]).count'), 0);
});

test('funnel preserves ordered AND intersections, deduplicates tags and handles empty steps', () => {
  const jobs = Array.from({length: 30}, (_, index) => ({
    required_skills: index < 28 ? ['Python', ...(index < 10 ? ['SQL'] : [])] : ['SQL']
  }));
  assert.deepEqual(evaluate("SkillAnalytics.funnel(jobs, [' Python ', 'SQL', 'PYTHON', 'missing', 'SQL'])", {jobs}), [
    {key: null, name: null, before: 30, count: 30, removed: 0, remainingShare: 1, retention: 1},
    {key: 'python', name: 'Python', before: 30, count: 28, removed: 2, remainingShare: 28 / 30, retention: 28 / 30},
    {key: 'sql', name: 'SQL', before: 28, count: 10, removed: 18, remainingShare: 10 / 30, retention: 10 / 28},
    {key: 'missing', name: 'missing', before: 10, count: 0, removed: 10, remainingShare: 0, retention: 0}
  ]);
  const empty = evaluate("SkillAnalytics.funnel([], ['Python', 'SQL'])");
  assert.equal(empty.length, 3);
  assert.ok(empty.every(step => step.count === 0 && step.remainingShare === null && step.retention === null));
});

test('roles use explicit role fields or title evidence without technology inference', () => {
  const jobs = [
    {role_specializations: ['Backend', 'backend'], title: 'Machine Learning Engineer'},
    {specialization: 'Python', required_skills: ['Python', 'Django', 'TensorFlow']},
    {specialization: 'Java', title: 'Senior back-end developer'},
    {title: 'Machine Learning Engineer'},
    {specialization: 'DevOps', title: 'SRE'},
    {title: 'Data Engineer / QA automation'},
    {title: 'Frontend developer, mobile Android'},
    {title: 'Full-stack Security Engineer'},
    {title: 'Python developer'}
  ];
  assert.deepEqual(evaluate('jobs.map(SkillAnalytics.rolesOf)', {jobs}), [
    ['Backend'], [], ['Backend'], ['ML'], ['DevOps'], ['Data', 'QA'], ['Frontend', 'Mobile'], ['Security', 'Fullstack'], []
  ]);
  const roles = evaluate('SkillAnalytics.roleOptions(jobs)', {jobs});
  assert.deepEqual(roles[0], {key: 'backend', name: 'Backend', count: 2});
  assert.ok(!roles.some(role => ['python', 'java'].includes(role.key)));
});

test('profile requires every skill and applies normalized exact role, level and location filters', () => {
  const jobs = [
    {id: 1, title: 'Backend developer', seniority: ' Senior ', location: 'Bratislava', required_skills: ['Python', 'SQL']},
    {id: 2, title: 'Backend developer', seniority: 'Senior', location: 'Bratislava', required_skills: ['Python']},
    {id: 3, title: 'ML Engineer', seniority: 'Senior', location: 'Bratislava', required_skills: ['Python', 'SQL']},
    {id: 4, title: 'Backend developer', seniority: 'Junior', location: 'Bratislava', required_skills: ['Python', 'SQL']},
    {id: 5, title: 'Backend developer', seniority: 'Senior', location: 'Bratislava region', required_skills: ['Python', 'SQL']}
  ];
  const profile = {skills: ['python', 'sql'], role: ' backend ', seniority: 'senior', location: ' BRATISLAVA '};
  assert.deepEqual(evaluate('SkillAnalytics.filterProfile(jobs, profile).map(job => job.id)', {jobs, profile}), [1]);
  assert.equal(evaluate('SkillAnalytics.filterProfile(jobs, {}).length', {jobs}), 5);
});

test('offer compares compatible gross minima with midrank ties and distinct salary coverage', () => {
  const jobs = [1000, 2000, 2000, 3000].map(salary_min => ({
    salary_min, salary_currency: 'EUR', salary_period: 'month', required_skills: ['Python'], company: 'Acme'
  }));
  jobs.push(
    {required_skills: ['Python'], company: 'Other', remote: true},
    {required_skills: ['Python'], salary_min: 5000, salary_currency: 'USD', salary_period: 'month'},
    {required_skills: ['Python'], salary_min: 20, salary_currency: 'EUR', salary_period: 'hour'},
    {required_skills: ['Python'], salary_min: 4000, salary_currency: 'EUR', salary_basis: ' NET '},
    {required_skills: ['Java'], salary_min: 9000, salary_currency: 'EUR'}
  );
  const profile = {skills: ['Python']};
  const offer = {amount: 2000, currency: 'EUR', period: 'month'};
  const result = evaluate('SkillAnalytics.compareOffer(jobs, profile, offer)', {jobs, profile, offer});
  assert.equal(result.count, 8);
  assert.equal(result.companies, 2);
  assert.equal(result.remoteCount, 1);
  assert.equal(result.salaryCount, 4);
  assert.equal(result.median, 2000);
  assert.equal(result.p25, 1750);
  assert.equal(result.p75, 2250);
  assert.deepEqual([result.below, result.equal, result.above, result.percentile], [1, 2, 1, 50]);
  assert.equal(result.differencePercent, 0);
  assert.equal(result.status, 'within_range');
  assert.equal(evaluate('SkillAnalytics.summarize(jobs).salaryGroups.find(group => group.currency === "EUR" && group.period === "month").max', {jobs}), 9000);
});

test('offer band boundaries include P25 and P75, with positive difference above median', () => {
  const jobs = [1000, 2000, 3000, 4000].map(salary_min => ({salary_min, salary_currency: 'EUR'}));
  const offers = [1000, 1750, 3250, 4000].map(amount => ({amount, currency: 'EUR', period: 'month'}));
  const results = evaluate('offers.map(offer => SkillAnalytics.compareOffer(jobs, {}, offer))', {jobs, offers});
  assert.deepEqual(results.map(result => result.status), ['below_range', 'within_range', 'within_range', 'above_range']);
  assert.equal(results[3].differencePercent, 60);
  assert.equal(results[0].percentile, 12.5);
});

test('invalid offers and missing compatible salary never manufacture zero estimates or NaN', () => {
  const jobs = [{salary_min: 2500, salary_currency: 'EUR', salary_period: 'month'}];
  const offers = [
    {amount: '2500', currency: 'EUR', period: 'month'},
    {amount: NaN, currency: 'EUR', period: 'month'},
    {amount: Infinity, currency: 'EUR', period: 'month'},
    {amount: 0, currency: 'EUR', period: 'month'},
    {amount: -1, currency: 'EUR', period: 'month'},
    {amount: 2500, currency: 'EUR', period: 'week'},
    {amount: 2500, currency: '', period: 'month'}
  ];
  const results = evaluate('offers.map(offer => SkillAnalytics.compareOffer(jobs, {}, offer))', {jobs, offers});
  assert.ok(results.every(result => !result.validOffer && result.status === 'invalid' && result.percentile === null && result.differencePercent === null));
  const noSalary = evaluate('SkillAnalytics.compareOffer(jobs, {}, {amount: 3000, currency: "USD", period: "month"})', {jobs});
  assert.equal(noSalary.status, 'no_salary');
  assert.equal(noSalary.count, 1);
  assert.equal(noSalary.salaryCount, 0);
  assert.equal(noSalary.median, null);
  const empty = evaluate('SkillAnalytics.compareOffer([], {}, {amount: 3000, currency: "EUR", period: "month"})');
  assert.equal(empty.status, 'no_salary');
  assert.equal(empty.percentile, null);
});

test('profile comparison uses independent AND profiles, shared denominator, units and overlap', () => {
  const jobs = [
    {id: 1, required_skills: ['Python', 'SQL'], title: 'Backend developer', salary_min: 2000, salary_currency: 'EUR'},
    {id: 2, required_skills: ['Python', 'SQL'], title: 'ML Engineer', salary_min: 4000, salary_currency: 'EUR'},
    {id: 3, required_skills: ['Python'], title: 'Backend developer', salary_min: 1000, salary_currency: 'EUR'},
    {id: 4, required_skills: ['Java'], title: 'Backend developer', salary_min: 8000, salary_currency: 'EUR'}
  ];
  const a = {skills: ['Python'], role: 'Backend'};
  const b = {skills: ['Python', 'SQL']};
  const unit = {currency: 'EUR', period: 'month'};
  const result = evaluate('SkillAnalytics.compareProfiles(jobs, a, b, unit)', {jobs, a, b, unit});
  assert.equal(result.a.count, 2);
  assert.equal(result.b.count, 2);
  assert.equal(result.a.share, 0.5);
  assert.equal(result.b.share, 0.5);
  assert.equal(result.overlap, 1);
  assert.equal(result.a.salary.median, 1500);
  assert.equal(result.b.salary.median, 3000);
  assert.equal(result.medianDifferencePercent, 100);
  const identical = evaluate('SkillAnalytics.compareProfiles(jobs, a, a, unit)', {jobs, a, unit});
  assert.equal(identical.overlap, 2);
  assert.equal(identical.medianDifferencePercent, 0);
  const missingUnit = evaluate('SkillAnalytics.compareProfiles(jobs, a, b, {currency: "USD", period: "month"})', {jobs, a, b});
  assert.equal(missingUnit.a.salary, null);
  assert.equal(missingUnit.medianDifferencePercent, null);
  const empty = evaluate('SkillAnalytics.compareProfiles([], {}, {}, {currency: "EUR", period: "month"})');
  assert.equal(empty.a.share, null);
  assert.equal(empty.b.share, null);
  assert.equal(empty.overlap, 0);
  assert.equal(empty.medianDifferencePercent, null);
});

test('salary conversion uses per-EUR cross rates and preserves same-currency values without rates', () => {
  const jobs = [
    {salary_min: 1200, salary_currency: 'USD', salary_period: 'month'},
    {salary_min: 1000, salary_currency: 'EUR'},
    {salary_min: 25000, salary_currency: 'CZK', salary_period: 'month'}
  ];
  const options = {currency: 'CZK', period: 'year', rates: {EUR: 1, USD: 1.2, CZK: 25}};
  assert.deepEqual(evaluate('jobs.map(job => SkillAnalytics.convertedSalary(job, options))', {jobs, options}), [300000, 300000, 300000]);
  assert.equal(evaluate('SkillAnalytics.convertedSalary(jobs[0], {currency: "USD", period: "year"})', {jobs}), 14400);
  assert.equal(evaluate('SkillAnalytics.convertedSalary(jobs[0], {currency: "EUR", period: "month"})', {jobs}), null);
});

test('monthly and hourly conversion round-trips use 52 weeks and explicit working hours', () => {
  const jobs = ['full_time', 'part-time', ' full time '].map(employment_type => ({
    salary_min: 2600, salary_currency: 'EUR', salary_period: 'month', employment_type
  }));
  const hourly = evaluate('jobs.map(job => SkillAnalytics.convertedSalary(job, {currency: "EUR", period: "hour"}))', {jobs});
  assert.deepEqual(hourly, [15, 30, 15]);
  const hourlyJobs = jobs.map((job, index) => ({...job, salary_min: hourly[index], salary_period: 'hour'}));
  assert.deepEqual(evaluate('jobs.map(job => SkillAnalytics.convertedSalary(job, {currency: "EUR", period: "month"}))', {jobs: hourlyJobs}), [2600, 2600, 2600]);
  assert.deepEqual(evaluate('jobs.map(job => SkillAnalytics.convertedSalary(job, {currency: "EUR", period: "year"}))', {jobs: hourlyJobs}), [31200, 31200, 31200]);
});

test('unknown employment excludes only conversions involving hours, without inventing work schedules', () => {
  const jobs = [undefined, 'contract', 'full_time/part_time'].map(employment_type => ({
    salary_min: 2400, salary_currency: 'EUR', salary_period: 'month', employment_type
  }));
  assert.deepEqual(evaluate('jobs.map(job => SkillAnalytics.convertedSalary(job, {currency: "EUR", period: "hour"}))', {jobs}), [null, null, null]);
  assert.deepEqual(evaluate('jobs.map(job => SkillAnalytics.convertedSalary(job, {currency: "EUR", period: "year"}))', {jobs}), [28800, 28800, 28800]);
  const hourlyJob = {salary_min: 15, salary_currency: 'USD', salary_period: 'hour'};
  assert.equal(evaluate('SkillAnalytics.convertedSalary(job, {currency: "EUR", period: "hour", rates: {USD: 1.2}})', {job: hourlyJob}), 12.5);
  assert.equal(evaluate('SkillAnalytics.convertedSalary(job, {currency: "EUR", period: "month", rates: {USD: 1.2}})', {job: hourlyJob}), null);
});

test('invalid salary observations, target units and unknown or invalid FX rates stay excluded', () => {
  const base = {salary_min: 2400, salary_currency: 'USD', salary_period: 'month', employment_type: 'full_time'};
  const options = {currency: 'EUR', period: 'year', rates: {USD: 1.2}};
  const jobs = [
    {...base, salary_min: '2400'}, {...base, salary_min: 0}, {...base, salary_min: -1},
    {...base, salary_min: Infinity}, {...base, salary_min: NaN}, {...base, salary_basis: 'NET'},
    {...base, salary_currency: ''}, {...base, salary_currency: 'XXX'}, {...base, salary_period: 'week'}
  ];
  assert.ok(evaluate('jobs.map(job => SkillAnalytics.convertedSalary(job, options))', {jobs, options}).every(value => value === null));
  for (const rate of [undefined, 0, -1, Infinity, NaN, '1.2']) {
    assert.equal(evaluate('SkillAnalytics.convertedSalary(job, options)', {job: base, options: {...options, rates: {USD: rate}}}), null);
  }
  for (const target of [{currency: '', period: 'year'}, {currency: 'EUR', period: 'week'}]) {
    assert.equal(evaluate('SkillAnalytics.convertedSalary(job, options)', {job: base, options: {...options, ...target}}), null);
  }
});

test('converted aggregate and trend count each usable posting once and report coverage', () => {
  const jobs = [
    {salary_min: 1200, salary_currency: 'USD', salary_period: 'month'},
    {salary_min: 24000, salary_currency: 'EUR', salary_period: 'year'},
    {salary_min: 15, salary_currency: 'EUR', salary_period: 'hour', employment_type: 'part_time'},
    {salary_min: 3000, salary_currency: 'EUR'},
    {salary_min: 20, salary_currency: 'EUR', salary_period: 'hour'},
    {salary_currency: 'EUR'}
  ].map(job => ({...job, parsed_at: '2026-11-10'}));
  const options = {currency: 'EUR', period: 'month', rates: {USD: 1.2}};
  const groups = evaluate('SkillAnalytics.salaryGroups(jobs, options)', {jobs, options});
  assert.equal(groups.length, 1);
  assert.deepEqual(groups[0], {currency: 'EUR', period: 'month', values: [1000, 1300, 2000, 3000],
    derivedCount: 3, excludedCount: 2, count: 4, median: 1650, p25: 1225, p75: 2250, min: 1000, max: 3000});
  assert.deepEqual(evaluate('SkillAnalytics.conversionCoverage(jobs, options)', {jobs, options}), {count: 4, derivedCount: 3, excludedCount: 2});
  assert.deepEqual(evaluate('SkillAnalytics.summarize(jobs, options).salaryGroups', {jobs, options}), groups);
  assert.deepEqual(evaluate('SkillAnalytics.trend(jobs, options)[0].salaryGroups', {jobs, options}), groups);
  assert.equal(evaluate('SkillAnalytics.trend(jobs, options)[0].count', {jobs, options}), 6);
});

test('converted offer and profile comparison share comparable units without duplicate samples', () => {
  const jobs = [
    {salary_min: 1200, salary_currency: 'USD', required_skills: ['Python']},
    {salary_min: 24000, salary_currency: 'EUR', salary_period: 'year', required_skills: ['Python', 'SQL']},
    {salary_min: 15, salary_currency: 'EUR', salary_period: 'hour', employment_type: 'full_time', required_skills: ['SQL']},
    {required_skills: ['Python']}
  ];
  const unit = {currency: 'EUR', period: 'month', rates: {USD: 1.2}, convert: true};
  const offer = evaluate('SkillAnalytics.compareOffer(jobs, {skills: ["Python"]}, {...unit, amount: 1500})', {jobs, unit});
  assert.deepEqual([offer.count, offer.salaryCount, offer.median, offer.percentile, offer.salaryDerivedCount, offer.salaryExcludedCount], [3, 2, 1500, 50, 2, 1]);
  const comparison = evaluate('SkillAnalytics.compareProfiles(jobs, {skills: ["Python"]}, {skills: ["SQL"]}, unit)', {jobs, unit});
  assert.equal(comparison.a.salary.count, 2);
  assert.equal(comparison.b.salary.count, 2);
  assert.equal(comparison.a.salary.median, 1500);
  assert.equal(comparison.b.salary.median, 2300);
  assert.equal(comparison.overlap, 1);
  assert.equal(comparison.a.salaryGroups.length, 1);
  assert.equal(comparison.medianDifferencePercent, 800 / 1500 * 100);
});
