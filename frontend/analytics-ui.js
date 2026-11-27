'use strict';

let analyticsSelected = [], analyticsExpanded = false, analyticsVisible = 10;
let analyticsJobs = [], analyticsPayKey = '';
const analyticsPayId = group => group.currency + ':' + group.period;

function analyticsSalaryOptions() {
  return {convert: true, currency: $('analytics-pay-currency').value || 'EUR', period: $('analytics-pay-period').value || 'month', rates: AnalyticsFX.rates()};
}

function renderAnalyticsSalaryControls() {
  const select = $('analytics-pay-currency');
  const current = select.value || 'EUR';
  const currencies = [...new Set([...Object.keys(AnalyticsFX.rates()), current,
    ...baseJobs.map(job => job.salary_currency?.toUpperCase()).filter(value => /^[A-Z]{3}$/.test(value || ''))])].sort();
  select.replaceChildren(...currencies.map(currency => {
    const option = element('option', currency); option.value = currency; return option;
  }));
  select.value = current;
  analyticsPayKey = current + ':' + $('analytics-pay-period').value;
  $('analytics-fx-source').textContent = AnalyticsFX.date() ? t('fxSource', {date: AnalyticsFX.date()}) : t('fxUnavailable');
  $('analytics-conversion-note').textContent = t('conversionMethod');
}

function syncAnalyticsSelection() {
  const available = new Set(SkillAnalytics.catalog(SkillAnalytics.eligibleJobs(baseJobs)).map(skill => skill.key));
  try {
    const saved = JSON.parse(readPreference('skillminer-analytics-skills-' + kind) || '[]');
    analyticsSelected = Array.isArray(saved) ? [...new Set(saved.filter(key => typeof key === 'string' && available.has(key)))] : [];
  } catch { analyticsSelected = []; }
}

function resetAnalyticsDataset() {
  analyticsSelected = [];
  analyticsExpanded = false;
  analyticsPayKey = '';
  analyticsVisible = 10;
  $('skill-search').value = $('analytics-from').value = $('analytics-to').value = '';
}

function selectAnalyticsSkill(key) {
  analyticsSelected = analyticsSelected.includes(key)
    ? analyticsSelected.filter(value => value !== key) : [...analyticsSelected, key];
  savePreference('skillminer-analytics-skills-' + kind, JSON.stringify(analyticsSelected));
  analyticsVisible = 10;
  renderSkillAnalytics();
  [...$('skill-catalog').querySelectorAll('button')].find(node => node.dataset.skillKey === key)?.focus({preventScroll: true});
}

function renderSkillCatalog() {
  const catalog = SkillAnalytics.catalog(SkillAnalytics.eligibleJobs(baseJobs));
  const query = $('skill-search').value.normalize('NFKC').trim().toLowerCase();
  const found = catalog.filter(skill => skill.key.includes(query));
  const shown = query || analyticsExpanded ? found : found.slice(0, 18);
  $('skill-catalog').replaceChildren();
  for (const skill of shown) {
    const chip = button('', () => selectAnalyticsSkill(skill.key), 'skill-chip');
    chip.dataset.skillKey = skill.key;
    chip.setAttribute('aria-pressed', String(analyticsSelected.includes(skill.key)));
    chip.append(element('span', skill.name), element('span', number(skill.count), 'skill-chip-count'));
    $('skill-catalog').append(chip);
  }
  if (!shown.length) $('skill-catalog').append(element('p', t('noSkillsFound'), 'empty'));
  $('skill-more').hidden = !!query || found.length <= 18;
  $('skill-more').textContent = analyticsExpanded ? t('showFewerSkills') : t('showAllSkills', {n: number(found.length)});
  $('skill-more').setAttribute('aria-expanded', String(analyticsExpanded));
  $('selected-skills').replaceChildren();
  if (!analyticsSelected.length) $('selected-skills').append(element('span', t('allSkills'), 'analytics-hint'));
  for (const key of analyticsSelected) {
    const name = catalog.find(skill => skill.key === key)?.name || key;
    const chip = button(name + ' ×', () => selectAnalyticsSkill(key), 'skill-chip selected');
    chip.setAttribute('aria-label', t('removeSkill', {skill: name}));
    $('selected-skills').append(chip);
  }
  $('skill-clear').disabled = !analyticsSelected.length;
}

function analyticsDateScope(jobs) {
  const days = Number($('period').value);
  const dates = jobs.map(SkillAnalytics.dateOf).filter(Boolean).sort();
  let from = $('analytics-from').value, to = $('analytics-to').value;
  if (days && dates.length) {
    const start = new Date(dates.at(-1) + 'T00:00:00Z');
    start.setUTCDate(start.getUTCDate() - days + 1);
    const cutoff = start.toISOString().slice(0, 10);
    from = from > cutoff ? from : cutoff;
  }
  return jobs.filter(job => {
    const date = SkillAnalytics.dateOf(job);
    return (!from && !to) || (date && (!from || date >= from) && (!to || date <= to));
  });
}

function analyticsGroup(groups) {
  return groups.find(group => analyticsPayId(group) === analyticsPayKey) || null;
}

function analyticsPlot(container, points, series, headers, rows, zero) {
  const nodes = [];
  if (!points.length || !points.some(point => series.some(item => Number.isFinite(point[item.key])))) {
    clearChart(container, element('p', t('noChartData'), 'empty'));
    return;
  }
  if (points.length === 1) nodes.push(element('p', t('singleDate'), 'analytics-hint'));
  const preview = element('p', '', 'analytics-chart-preview');
  nodes.push(chart(points, series, {zero, preview: point => {
    preview.textContent = point ? [day(point.at), ...series.map(item => item.label + ': ' + (point[item.key] == null ? '—' : number(point[item.key])))].join(' · ') : '';
  }}), preview, chartTable(headers, rows));
  clearChart(container, ...nodes);
}

function renderSkillTrend(jobs) {
  const trend = SkillAnalytics.trend(jobs, analyticsSalaryOptions());
  const countSeries = [{key: 'count', label: t('matchingJobs'), color: '--accent'}];
  const points = trend.map(point => ({...point, at: Date.parse(point.date + 'T00:00:00Z')}));
  analyticsPlot($('activity'), points, countSeries, [t('date'), t('matchingJobs')],
    points.map(point => [day(point.at), number(point.count)]), true);
  const payPoints = points.map(point => ({at: point.at, ...analyticsGroup(point.salaryGroups)}));
  const paySeries = [{key: 'median', label: t('medianMinimum'), color: '--accent'},
    {key: 'p25', label: 'P25', color: '--blue'}, {key: 'p75', label: 'P75', color: '--green'}];
  analyticsPlot($('analytics-pay-trend'), payPoints, paySeries,
    [t('date'), t('medianMinimum'), 'P25', 'P75', t('sample')],
    payPoints.map(point => [day(point.at), ...['median', 'p25', 'p75', 'count'].map(key => point[key] == null ? '—' : number(point[key]))]), false);
  const kinds = new Set(jobs.map(SkillAnalytics.dateKind));
  $('analytics-date-note').textContent = t(kinds.has('parsed') ? 'parsedDateNote' : kinds.has('scraped') ? 'scrapedDateNote' : 'publishedDateNote');
  if (kinds.has('missing')) $('analytics-date-note').textContent += ' ' + t('missingDateNote');
}

function renderAnalyticsHistogram(group) {
  const container = $('analytics-histogram');
  container.replaceChildren();
  $('analytics-pay-range').textContent = group
    ? t('salaryRange', {p25: number(group.p25), p75: number(group.p75), unit: unit(group.currency, group.period)}) : t('noSalaryData');
  if (!group) { container.append(element('p', t('noSalaryData'), 'empty')); return; }
  const bins = group.min === group.max ? 1 : Math.min(7, Math.ceil(Math.sqrt(group.count)));
  const width = (group.max - group.min) / bins || 1;
  const counts = Array(bins).fill(0);
  for (const value of group.values) counts[Math.min(bins - 1, Math.floor((value - group.min) / width))] += 1;
  bars(container, counts.map((count, i) => [bins === 1 ? number(group.min)
    : number(group.min + i * width, {maximumFractionDigits: 0}) + '–' + number(group.min + (i + 1) * width, {maximumFractionDigits: 0}), count]), Math.max(...counts));
}

function renderAnalyticsResults() {
  const options = analyticsSalaryOptions();
  const shown = analyticsJobs.slice(0, analyticsVisible);
  const rows = shown.map(job => {
    const title = button(job.title, () => detail(job));
    const stack = element('div', '', 'analytics-result-skills');
    stack.append(...SkillAnalytics.skillsOf(job).map(skill => {
      const selected = analyticsSelected.includes(skill.normalize('NFKC').toLowerCase().trim());
      return element('span', skill, 'tag' + (selected ? ' analytics-highlight' : ''));
    }));
    const pay = element('div');
    const amount = SkillAnalytics.convertedSalary(job, options);
    pay.append(element('span', amount == null ? '—' : number(amount, {maximumFractionDigits: 2}) + '+ ' + unit(options.currency, options.period)));
    pay.append(element('small', t('convertedOriginal') + ': ' + salary(job) + (salaryUnit(job) ? ' · ' + salaryUnit(job) : ''), 'cell-note'));
    return [title, job.company, pay, stack];
  });
  $('analytics-results').replaceChildren(rows.length ? table([t('position'), t('company'), t('salary'), t('chooseSkills')], rows)
    : element('p', t('noSkillMatches'), 'empty'));
  $('analytics-result-count').textContent = number(analyticsJobs.length);
  $('analytics-more').hidden = analyticsVisible >= analyticsJobs.length;
}

function renderSkillAnalytics() {
  const eligible = SkillAnalytics.eligibleJobs(baseJobs);
  const scoped = analyticsDateScope(eligible);
  analyticsJobs = SkillAnalytics.matchingJobs(scoped, analyticsSelected);
  renderAnalyticsSalaryControls();
  const summary = SkillAnalytics.summarize(analyticsJobs, analyticsSalaryOptions());
  $('analytics-kind').textContent = t(kind === 'real' ? 'dataReal' : 'dataMock');
  $('analytics-quality').textContent = t('checkedScope', {n: number(eligible.length), total: number(baseJobs.length)});
  renderSkillCatalog();
  $('analytics-scope').textContent = $('analytics-from').value && $('analytics-to').value && $('analytics-from').value > $('analytics-to').value
    ? t('invalidDateRange') : t('scopeNote', {n: number(scoped.length)});
  const groups = summary.salaryGroups;
  const group = analyticsGroup(groups);
  $('analytics-count').textContent = number(summary.count);
  $('analytics-total').textContent = t('outOfJobs', {n: number(scoped.length)});
  $('analytics-share').textContent = scoped.length ? number(summary.count / scoped.length, {style: 'percent', maximumFractionDigits: 1}) : '—';
  $('analytics-median').textContent = group ? number(group.median, {maximumFractionDigits: group.period === 'hour' ? 2 : 0}) : '—';
  $('analytics-pay-sample').textContent = unit(analyticsSalaryOptions().currency, analyticsSalaryOptions().period) + ' · ' + t('salaryCoverageShort', {n: number(group?.count || 0), total: number(summary.count)});
  $('analytics-pay-coverage').textContent = t('conversionCoverage', {n: number(group?.count || 0), total: number(summary.count), excluded: number(summary.count - (group?.count || 0))});
  $('analytics-companies').textContent = number(summary.companies);
  $('analytics-remote').textContent = t('remote') + ': ' + (summary.count ? number(summary.remoteCount / summary.count, {style: 'percent', maximumFractionDigits: 0}) : '—');
  $('analytics-empty').hidden = !!summary.count;
  bars($('bars'), rank(analyticsJobs, job => (rankMode === 'nice' ? job.nice_to_have_skills : job.required_skills) ?? []), summary.count);
  bars($('distribution'), rank(analyticsJobs, job => [job[$('group-by').value] || t('unknown')]), summary.count);
  const salaryOptions = analyticsSalaryOptions();
  const convertedJobs = analyticsJobs.flatMap(job => {
    const amount = SkillAnalytics.convertedSalary(job, salaryOptions);
    return amount == null ? [] : [{...job, salary_min: amount, salary_currency: salaryOptions.currency, salary_period: salaryOptions.period}];
  });
  renderPayComparison(convertedJobs);
  renderActivity(analyticsJobs);
  renderAnalyticsHistogram(group);
  renderAnalyticsResults();
  renderSkillFunnel(scoped);
  renderSkillComparisons(scoped);
}

function initSkillAnalytics() {
  $('period').value = '0';
  $('skill-search').addEventListener('input', renderSkillCatalog);
  $('skill-clear').addEventListener('click', () => {
    analyticsSelected = []; analyticsVisible = 10;
    savePreference('skillminer-analytics-skills-' + kind, '[]'); renderSkillAnalytics();
  });
  $('skill-more').addEventListener('click', () => { analyticsExpanded = !analyticsExpanded; renderSkillCatalog(); });
  for (const id of ['analytics-from', 'analytics-to']) $(id).addEventListener('change', () => { analyticsVisible = 10; renderSkillAnalytics(); });
  for (const id of ['analytics-pay-currency', 'analytics-pay-period']) $(id).addEventListener('change', renderSkillAnalytics);
  AnalyticsFX.ready.then(() => { if (state) renderSkillAnalytics(); });
  $('analytics-more').addEventListener('click', () => { analyticsVisible += 10; renderAnalyticsResults(); });
}
