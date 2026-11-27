'use strict';

let comparisonScope = [], comparisonKind = null, comparisonState, comparisonInitialized = false;
const comparisonPrefixes = ['offer', 'profile-a', 'profile-b'];
const emptyComparisonProfile = () => ({skills: [], role: '', seniority: '', location: ''});
const comparisonSkillKey = value => value.normalize('NFKC').trim().replace(/\s+/g, ' ').toLowerCase();

function loadComparisonState() {
  if (comparisonKind === kind) return;
  comparisonKind = kind;
  let saved;
  try { saved = JSON.parse(readPreference('skillminer-comparisons-' + kind) || '{}'); } catch { saved = {}; }
  comparisonState = {profiles: {}, offer: {amount: '', currency: 'EUR', period: 'month'}, unit: {currency: 'EUR', period: 'month'}};
  for (const prefix of comparisonPrefixes) {
    const input = saved?.profiles?.[prefix];
    comparisonState.profiles[prefix] = {
      skills: Array.isArray(input?.skills) ? [...new Set(input.skills.filter(value => typeof value === 'string').map(comparisonSkillKey))] : [],
      role: typeof input?.role === 'string' ? input.role : '',
      seniority: typeof input?.seniority === 'string' ? input.seniority : '',
      location: typeof input?.location === 'string' ? input.location : ''
    };
    $(prefix + '-skill-search').value = '';
  }
  if (typeof saved?.offer?.amount === 'string') comparisonState.offer.amount = saved.offer.amount;
  for (const field of ['offer', 'unit']) {
    if (/^[A-Z]{3}$/.test(saved?.[field]?.currency || '')) comparisonState[field].currency = saved[field].currency;
    if (['month', 'year', 'hour'].includes(saved?.[field]?.period)) comparisonState[field].period = saved[field].period;
  }
  $('offer-amount').value = comparisonState.offer.amount;
  $('offer-period').value = comparisonState.offer.period;
  $('profiles-period').value = comparisonState.unit.period;
}

function saveComparisonState() {
  savePreference('skillminer-comparisons-' + kind, JSON.stringify(comparisonState));
}

function comparisonOptions(select, values, current, blankLabel) {
  const options = [...new Set(values.filter(value => typeof value === 'string' && value))].sort((a, b) => a.localeCompare(b));
  if (current && !options.includes(current)) options.push(current);
  select.replaceChildren();
  if (blankLabel) { const option = element('option', blankLabel); option.value = ''; select.append(option); }
  for (const value of options) { const option = element('option', value); option.value = value; select.append(option); }
  select.value = current;
}

function changeComparisonProfile(prefix, action) {
  action(comparisonState.profiles[prefix]);
  saveComparisonState();
  renderComparisonControls(prefix);
  renderComparisonResults();
}

function renderComparisonSkills(prefix) {
  const profile = comparisonState.profiles[prefix];
  const catalog = SkillAnalytics.catalog(comparisonScope);
  const selected = $(prefix + '-skills');
  selected.replaceChildren();
  if (!profile.skills.length) selected.append(element('span', t('profileAllSkills'), 'analytics-hint'));
  for (const key of profile.skills) {
    const name = catalog.find(skill => skill.key === key)?.name || key;
    const chip = button(name + ' ×', () => changeComparisonProfile(prefix, current => { current.skills = current.skills.filter(value => value !== key); }), 'skill-chip selected');
    chip.setAttribute('aria-label', t('removeSkill', {skill: name}));
    selected.append(chip);
  }
  const query = comparisonSkillKey($(prefix + '-skill-search').value);
  const choices = catalog.filter(skill => skill.key.includes(query)).slice(0, query ? 12 : 6);
  const container = $(prefix + '-skill-options');
  container.replaceChildren();
  for (const skill of choices) {
    const chip = button(skill.name + ' · ' + number(skill.count), () => changeComparisonProfile(prefix, current => {
      current.skills = current.skills.includes(skill.key) ? current.skills.filter(key => key !== skill.key) : [...current.skills, skill.key];
    }), 'skill-chip');
    chip.setAttribute('aria-pressed', String(profile.skills.includes(skill.key)));
    container.append(chip);
  }
  if (!choices.length) container.append(element('p', t('noMatchingSkill'), 'analytics-hint'));
}

function renderComparisonControls(prefix) {
  renderComparisonSkills(prefix);
  const profile = comparisonState.profiles[prefix];
  comparisonOptions($(prefix + '-role'), SkillAnalytics.roleOptions(comparisonScope).map(role => role.name), profile.role, t('anyRole'));
  comparisonOptions($(prefix + '-seniority'), comparisonScope.map(job => job.seniority), profile.seniority, t('allFilterValues'));
  comparisonOptions($(prefix + '-location'), comparisonScope.map(job => job.location).filter(value => !/^(null|undefined)$/i.test(value || '')), profile.location, t('allFilterValues'));
}

function initComparisonControls() {
  if (comparisonInitialized) return;
  comparisonInitialized = true;
  for (const prefix of comparisonPrefixes) {
    const host = $(prefix + '-profile-controls');
    host.innerHTML = `
      <div id="${prefix}-skills" class="skill-chips comparison-selected" aria-live="polite"></div>
      <label><span class="sr-only" data-i18n="profileSearch"></span><input type="search" id="${prefix}-skill-search" data-i18n-placeholder="profileSearch" autocomplete="off"></label>
      <div id="${prefix}-skill-options" class="skill-chips comparison-options" role="group" data-i18n-aria="chooseSkills"></div>
      <div class="profile-actions"><button type="button" id="${prefix}-copy" class="link-button" data-i18n="copyCurrentSkills"></button><button type="button" id="${prefix}-clear" class="link-button" data-i18n="clearProfile"></button></div>
      <div class="profile-filters"><label><span data-i18n="roleFilter"></span><select id="${prefix}-role"></select></label><label><span data-i18n="seniority"></span><select id="${prefix}-seniority"></select></label><label><span data-i18n="location"></span><select id="${prefix}-location"></select></label></div>`;
    for (const node of host.querySelectorAll('[data-i18n]')) node.textContent = t(node.dataset.i18n);
    for (const node of host.querySelectorAll('[data-i18n-placeholder]')) node.placeholder = t(node.dataset.i18nPlaceholder);
    for (const node of host.querySelectorAll('[data-i18n-aria]')) node.setAttribute('aria-label', t(node.dataset.i18nAria));
    $(prefix + '-skill-search').addEventListener('input', () => renderComparisonSkills(prefix));
    for (const field of ['role', 'seniority', 'location']) $(prefix + '-' + field).addEventListener('change', event => {
      comparisonState.profiles[prefix][field] = event.target.value; saveComparisonState(); renderComparisonResults();
    });
    $(prefix + '-copy').addEventListener('click', () => changeComparisonProfile(prefix, profile => { profile.skills = [...analyticsSelected]; }));
    $(prefix + '-clear').addEventListener('click', () => changeComparisonProfile(prefix, profile => { Object.assign(profile, emptyComparisonProfile()); }));
  }
  $('offer-amount').addEventListener('input', event => { comparisonState.offer.amount = event.target.value; saveComparisonState(); renderCompanyOffer(); });
  for (const [prefix, key] of [['offer', 'offer'], ['profiles', 'unit']]) for (const field of ['currency', 'period']) {
    $(prefix + '-' + field).addEventListener('change', event => { comparisonState[key][field] = event.target.value; saveComparisonState(); renderComparisonResults(); });
  }
  for (const [prefix, role] of [['profile-a', 'Backend'], ['profile-b', 'ML']]) $(prefix + '-example').addEventListener('click', () => {
    changeComparisonProfile(prefix, profile => { Object.assign(profile, emptyComparisonProfile(), {skills: ['python'], role}); });
  });
}

function renderSkillFunnel(scoped) {
  const rows = SkillAnalytics.funnel(scoped, analyticsSelected);
  const container = $('skill-funnel');
  container.replaceChildren();
  rows.forEach((step, index) => {
    const card = element('div', '', 'funnel-step' + (index === rows.length - 1 ? ' is-final' : ''));
    card.append(element('span', index ? '+ ' + step.name : t('funnelBaseline'), 'funnel-name'), element('strong', number(step.count)));
    if (index) {
      card.append(element('span', t('funnelRemoved', {n: number(step.removed)}), 'funnel-removed'));
      card.append(element('small', t('funnelRetained', {share: step.retention == null ? '—' : number(step.retention, {style: 'percent', maximumFractionDigits: 1})})));
    }
    const track = element('div', '', 'funnel-track');
    const fill = element('span'); fill.style.width = 100 * (step.remainingShare || 0) + '%'; track.append(fill); card.append(track);
    container.append(card);
  });
  $('skill-funnel-note').textContent = t(analyticsSelected.length ? 'funnelOrder' : 'funnelNoSkills');
}

function comparisonMetric(label, value, note = '') {
  const card = element('div', '', 'comparison-metric');
  card.append(element('span', label), element('strong', value));
  if (note) card.append(element('small', note));
  return card;
}

function renderCompanyOffer() {
  const offer = comparisonState.offer;
  const result = SkillAnalytics.compareOffer(comparisonScope, comparisonState.profiles.offer, {
    amount: offer.amount.trim() ? Number(offer.amount) : null, currency: offer.currency, period: offer.period,
    convert: true, rates: AnalyticsFX.rates()
  });
  const container = $('offer-result');
  container.replaceChildren(element('h3', t('compareOfferResult')));
  const statusKey = {invalid: 'offerEnterAmount', no_salary: 'offerNoSalary', below_range: 'offerBelow', within_range: 'offerWithin', above_range: 'offerAbove'}[result.status];
  const status = element('p', t(statusKey), 'offer-status'); status.dataset.status = result.status; container.append(status);
  container.append(element('p', t('comparisonPaySample', {n: number(result.salaryCount), total: number(result.count)}), 'analytics-hint'));
  const amountUnit = unit(offer.currency, offer.period);
  const metrics = element('div', '', 'offer-metrics');
  metrics.append(comparisonMetric(t('yourOffer'), result.validOffer ? number(result.offerAmount) : '—', amountUnit),
    comparisonMetric(t('medianMinimum'), result.median == null ? '—' : number(result.median), amountUnit),
    comparisonMetric(t('offerDifference'), result.differencePercent == null ? '—' : number(result.differencePercent / 100, {style: 'percent', signDisplay: 'exceptZero', maximumFractionDigits: 1})));
  container.append(metrics);
  if (result.percentile != null) {
    const caption = element('div', '', 'offer-percentile-label'); caption.append(t('offerPercentile'), element('strong', number(result.percentile / 100, {style: 'percent', maximumFractionDigits: 1})));
    const gauge = element('div', '', 'offer-percentile');
    const marker = element('span', '', 'offer-marker'); marker.style.left = Math.min(99, Math.max(1, result.percentile)) + '%'; gauge.append(marker);
    gauge.setAttribute('role', 'img'); gauge.setAttribute('aria-label', caption.textContent);
    const scale = element('div', '', 'offer-percentile-scale'); scale.append(...['0%', '25%', '50%', '75%', '100%'].map(text => element('span', text)));
    container.append(caption, gauge, scale, element('p', t('offerCounts', {below: number(result.below), equal: number(result.equal), above: number(result.above)}), 'analytics-hint'));
    container.append(element('p', t('middleRange') + ': ' + number(result.p25) + '–' + number(result.p75) + ' ' + amountUnit, 'analytics-hint'));
  }
  container.append(element('p', t('offerPercentileMethod'), 'analytics-hint'));
}

function renderProfileComparison() {
  const unitChoice = comparisonState.unit;
  const result = SkillAnalytics.compareProfiles(comparisonScope, comparisonState.profiles['profile-a'], comparisonState.profiles['profile-b'], {...unitChoice, convert: true, rates: AnalyticsFX.rates()});
  const profileNames = [t('profileA'), t('profileB')];
  bars($('profiles-count-chart'), [[profileNames[0], result.a.count], [profileNames[1], result.b.count]], Math.max(1, result.a.count, result.b.count));
  const pay = [result.a.salary, result.b.salary];
  const values = pay.map((group, index) => group ? [profileNames[index], group.median] : null).filter(Boolean);
  $('profiles-pay-title').textContent = t('comparisonPay') + ' · ' + unit(unitChoice.currency, unitChoice.period);
  if (values.length) bars($('profiles-pay-chart'), values, Math.max(1, ...values.map(row => row[1])));
  else $('profiles-pay-chart').replaceChildren(element('p', t('comparisonNoDifference'), 'analytics-hint'));
  const share = value => value == null ? '—' : number(value, {style: 'percent', maximumFractionDigits: 1});
  const value = (profile, field) => profile.salary ? number(profile.salary[field]) : '—';
  const rows = [
    [t('matchingJobs'), number(result.a.count), number(result.b.count)],
    [t('profileSampleShare'), share(result.a.share), share(result.b.share)],
    [t('company'), number(result.a.companies), number(result.b.companies)],
    [t('remote'), share(result.a.count ? result.a.remoteCount / result.a.count : null), share(result.b.count ? result.b.remoteCount / result.b.count : null)],
    [t('profileSalaryCount'), number(result.a.salary?.count || 0), number(result.b.salary?.count || 0)],
    [t('medianMinimum'), value(result.a, 'median'), value(result.b, 'median')],
    [t('middleRange'), pay[0] ? number(pay[0].p25) + '–' + number(pay[0].p75) : '—', pay[1] ? number(pay[1].p25) + '–' + number(pay[1].p75) : '—']
  ];
  $('profiles-table').replaceChildren(table(['', ...profileNames], rows));
  $('profiles-overlap').textContent = t('comparisonOverlap', {n: number(result.overlap)});
  $('profiles-difference').textContent = result.medianDifferencePercent == null ? t('comparisonNoDifference')
    : t('comparisonDifference', {difference: number(result.medianDifferencePercent / 100, {style: 'percent', signDisplay: 'exceptZero', maximumFractionDigits: 1})});
}

function renderComparisonResults() { renderCompanyOffer(); renderProfileComparison(); }

function renderSkillComparisons(scoped) {
  initComparisonControls();
  comparisonScope = scoped;
  loadComparisonState();
  for (const prefix of comparisonPrefixes) renderComparisonControls(prefix);
  const currencies = [...Object.keys(AnalyticsFX.rates()), 'EUR', 'USD', 'CZK', 'GBP', ...scoped.map(job => job.salary_currency).filter(value => /^[A-Z]{3}$/.test(value || ''))];
  comparisonOptions($('offer-currency'), currencies, comparisonState.offer.currency);
  comparisonOptions($('profiles-currency'), currencies, comparisonState.unit.currency);
  $('profile-a-example').textContent = t('exampleProfile', {name: 'Python + Backend'});
  $('profile-b-example').textContent = t('exampleProfile', {name: 'Python + ML'});
  renderComparisonResults();
}
