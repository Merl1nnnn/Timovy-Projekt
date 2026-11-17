'use strict';

const $ = id => document.getElementById(id);
const number = (value, options) => new Intl.NumberFormat(MESSAGES[language].locale, options).format(value);
const day = at => new Intl.DateTimeFormat(MESSAGES[language].locale, {
  day: 'numeric', month: 'short', timeZone: 'UTC'
}).format(at);
const dateTime = at => new Intl.DateTimeFormat(MESSAGES[language].locale, {
  dateStyle: 'medium', timeStyle: 'short'
}).format(at);
const colors = ['--accent', '--blue', '--green'];
const statePrefix = 'skillminer-history-v1-';
const routes = {overview: 'overview', postings: 'postings', analytics: 'analytics',
  settings: 'settings', about: 'about'};
const filterRoutes = new Set(['overview', 'postings', 'analytics']);
let pageSize = Number(restoreSelection('rows-per-page', 'skillminer-page-size'));
$('period').value = restoreSelection('default-period', 'skillminer-default-period');
let preferredMode = readPreference('skillminer-mode');
if (!['light', 'dark'].includes(preferredMode)) preferredMode = null;
let dataset, state, baseJobs = [], visible = pageSize, selectedJob, selectedPeriod;
let loadError, pending, mockStatus, mockRequest, listedJobs = [];
let activeScreen;

function restoreSelection(id, key) {
  const select = $(id);
  const preference = readPreference(key);
  if ([...select.options].some(option => option.value === preference)) select.value = preference;
  return select.value;
}

function element(tag, value = '', className = '') {
  const node = document.createElement(tag);
  node.textContent = value;
  if (className) node.className = className;
  return node;
}

function button(label, action, className = 'link-button') {
  const node = element('button', label, className);
  node.type = 'button';
  node.addEventListener('click', action);
  return node;
}

function salary(job) {
  const {salary_min: min, salary_max: max, salary_currency: currency} = job;
  if (min == null && max == null) return '—';
  const range = min == null ? '≤ ' + number(max)
    : max == null ? number(min) + '+' : number(min) + '–' + number(max);
  return [range, currency].filter(Boolean).join(' ');
}

function unit(currency, period) {
  return currency + ' / ' + (MESSAGES[language][period] ?? period);
}

function salaryUnit(job) {
  return job.salary_currency ? unit(job.salary_currency, job.salary_period || 'month') : '';
}

function sourceLink(job, label) {
  const url = originalUrl(job.source_url);
  const demo = dataset?.dataset_kind === 'synthetic';
  if (!demo && !url) return element('span', label, 'cell-note');
  const link = element('a', label, 'source-link');
  if (demo) {
    link.href = '#';
    link.setAttribute('aria-disabled', 'true');
    link.addEventListener('click', event => event.preventDefault());
    link.title = t('demoLink');
  } else {
    link.href = url.href;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
  }
  return link;
}

function matches(job) {
  const query = $('search').value.trim().toLocaleLowerCase();
  const searchable = [job.title, job.company, job.location, ...(job.technologies ?? []), ...(job.required_skills ?? [])]
    .join(' ').toLocaleLowerCase();
  return (!query || searchable.includes(query)) && filterFields.every(field => {
    const value = $(field).value;
    if (!value) return true;
    if (field === 'site') return job.sources.some(source => source.site === value);
    return job[field] === value;
  }) && (!$('doubtful').checked || job.low_confidence)
    && (!$('duplicates').checked || job.possibleDuplicates.length > 0);
}

function populateFilters() {
  for (const field of filterFields.filter(field => field !== 'company_size')) {
    const select = $(field);
    const selected = select.value;
    const values = new Set(field === 'site'
      ? baseJobs.flatMap(job => job.sources.map(source => source.site))
      : baseJobs.map(job => job[field]));
    select.replaceChildren(select.options[0]);
    for (const value of [...values].filter(Boolean).sort((a, b) => a.localeCompare(b))) {
      const option = element('option', value);
      option.value = value;
      select.append(option);
    }
    select.value = values.has(selected) ? selected : '';
  }
}

function formatChange(field, value) {
  if (value == null) return '—';
  if (Array.isArray(value)) return value.join(', ') || '—';
  if (typeof value === 'boolean') return t(value ? 'yes' : 'no');
  if (typeof value === 'number') return number(value);
  return MESSAGES[language][value] ?? value;
}

function changesList(event) {
  const list = element('ul');
  const payFields = ['salary_min', 'salary_max', 'salary_currency', 'salary_period'];
  if (event.fields.some(field => payFields.includes(field))) {
    const before = [salary(event.before), salaryUnit(event.before).split(' / ')[1]].filter(Boolean).join(' / ');
    const after = [salary(event.job), salaryUnit(event.job).split(' / ')[1]].filter(Boolean).join(' / ');
    list.append(element('li', t('salary') + ' · ' + before + ' → ' + after));
  }
  for (const field of event.fields.filter(field => !payFields.includes(field))) {
    list.append(element('li', t(field === 'title' ? 'titleField' : field) + ' · '
      + formatChange(field, event.before[field]) + ' → ' + formatChange(field, event.job[field])));
  }
  return list;
}

function renderChanges(jobs) {
  const bySource = new Map(jobs.flatMap(job => job.sources.map(source => [source.key, job])));
  const entries = updates(state.history).filter(event => bySource.has(event.key));
  $('change-count').textContent = number(entries.length);
  $('change-list').replaceChildren();
  if (!entries.length) $('change-list').append(element('p', t('noChanges'), 'empty'));
  for (const event of entries) {
    const card = element('article', '', 'change');
    const row = element('div');
    const job = bySource.get(event.key);
    const target = job.key === event.key && job.source_url === event.job.source_url
      ? job : {...event.job, sources: [event.job], possibleDuplicates: job.possibleDuplicates};
    row.append(button(event.job.title, () => detail(target)), element('time', dateTime(event.at), 'cell-note'));
    card.append(row, changesList(event));
    $('change-list').append(card);
  }
}

function renderMetrics(jobs) {
  $('count').textContent = number(jobs.length);
  $('skills').textContent = number(new Set(jobs.flatMap(job => job.technologies ?? [])).size);
  $('review').textContent = number(jobs.filter(job => job.low_confidence).length);
  $('remote').textContent = jobs.length
    ? number(jobs.filter(job => job.remote).length / jobs.length, {style: 'percent'}) : '—';
}

function table(headers, rows) {
  const wrapper = element('div', '', 'table-wrap');
  const node = element('table');
  const header = node.createTHead().insertRow();
  for (const label of headers) {
    const th = element('th', label);
    th.scope = 'col';
    header.append(th);
  }
  const body = node.createTBody();
  for (const values of rows) {
    const row = body.insertRow();
    for (const value of values) {
      const cell = row.insertCell();
      if (value instanceof Node) cell.append(value);
      else cell.textContent = value;
    }
  }
  wrapper.append(node);
  return wrapper;
}

function renderPostings(jobs) {
  listedJobs = selectedPeriod?.jobs ?? jobs;
  $('shown').textContent = number(listedJobs.length);
  $('job-table').hidden = !listedJobs.length;
  $('status').replaceChildren();
  $('status').hidden = Boolean(listedJobs.length && !selectedPeriod);
  if (selectedPeriod) {
    $('status').append(t('showingPeriod', {period: periodLabel(selectedPeriod)}) + ' · ',
      button(t('clearPeriod'), () => { selectedPeriod = null; renderPostings(jobs); }));
  }
  if (!listedJobs.length) $('status').append(t('empty'));
  $('jobs').replaceChildren();
  for (const job of listedJobs.slice(0, visible)) {
    const row = $('jobs').insertRow();
    const titleCell = row.insertCell();
    titleCell.append(button(job.title, () => detail(job), 'link-button job-title'));
    const info = [job.location, job.seniority, job.specialization].filter(Boolean).join(' · ');
    if (info) titleCell.append(element('small', info, 'cell-note'));
    if (job.low_confidence) titleCell.append(element('span', t('needsReview'), 'flag'));
    if (job.possibleDuplicates.length) titleCell.append(element('span', t('possibleDuplicates'), 'flag'));
    const companyCell = row.insertCell();
    companyCell.append(job.company || '—', element('small',
      job.company_headcount ? t('headcount', {n: number(job.company_headcount)}) : t('unknown'), 'cell-note'));
    const payCell = row.insertCell();
    payCell.className = 'pay-cell';
    payCell.append(salary(job));
    if (salaryUnit(job)) payCell.append(element('small', salaryUnit(job), 'cell-note'));
    const sourceCell = row.insertCell();
    sourceCell.append(sourceLink(job, (job.site || t('site')) + ' ↗'));
    if (job.sources.length > 1) {
      sourceCell.append(element('small', t('copies', {n: number(job.sources.length)}), 'cell-note'));
    }
  }
  $('more').hidden = listedJobs.length <= visible;
  $('export').disabled = !listedJobs.length;
}

function bars(container, entries, total) {
  container.replaceChildren();
  container.className = 'bars';
  if (!entries.length) container.append(element('p', t('empty'), 'empty'));
  for (const [label, count] of entries) {
    const line = element('div');
    const legend = element('div', '', 'bar-label');
    legend.append(element('span', label), element('span', number(count)));
    const track = element('div', '', 'bar-track');
    const fill = element('div', '', 'bar-fill');
    fill.style.width = 100 * count / (total || 1) + '%';
    track.append(fill);
    line.append(legend, track);
    container.append(line);
  }
}

function rank(jobs, groups) {
  const counts = new Map();
  for (const job of jobs) {
    for (const label of new Set(groups(job))) counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 8);
}

const charts = new WeakMap();
const chartObserver = new ResizeObserver(entries => {
  for (const {target} of entries) charts.get(target)?.();
});

function clearChart(container, ...nodes) {
  for (const canvas of container.querySelectorAll('canvas')) chartObserver.unobserve(canvas);
  container.replaceChildren(...nodes);
}

function chart(points, series, opts) {
  const canvas = element('canvas', '', 'chart-canvas');
  canvas.setAttribute('aria-hidden', 'true');
  let selected = -1;
  let x = [];
  function draw() {
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (!width || !height) return;
    const scale = devicePixelRatio || 1;
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    const ctx = canvas.getContext('2d');
    ctx.scale(scale, scale);
    const style = getComputedStyle(canvas);
    const colors = series.map(item => style.getPropertyValue(item.color).trim());
    const values = points.flatMap(point => series.map(item => point[item.key])).filter(Number.isFinite);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const min = opts.zero ? 0 : Math.max(0, Math.floor(minValue * .95));
    const max = Math.max(min + 1, maxValue);
    const top = 13;
    const bottom = height - 27;
    ctx.font = '12.1px Inter, system-ui, sans-serif';
    const left = Math.max(35, ctx.measureText(number(max)).width + 12);
    const right = Math.max(left + 1, width - 25);
    const first = points[0].at;
    const last = points.at(-1).at;
    x = points.map(point => first === last ? (left + right) / 2 : left + (right - left) * (point.at - first) / (last - first));
    const y = value => bottom - (bottom - top) * (value - min) / (max - min);
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    const ticks = Math.min(4, Math.max(1, Math.round(max - min)));
    for (let i = 0; i <= ticks; i++) {
      const value = Math.round(min + (max - min) * i / ticks);
      const line = y(value);
      ctx.strokeStyle = style.getPropertyValue('--line').trim();
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(left, line);
      ctx.lineTo(right, line);
      ctx.stroke();
      ctx.fillStyle = style.getPropertyValue('--muted').trim();
      ctx.fillText(number(value), left - 7, line);
    }
    ctx.textAlign = 'center';
    let lastLabel = -Infinity;
    points.forEach((point, i) => {
      if (i === points.length - 1 || (x[i] - lastLabel >= 75 && x.at(-1) - x[i] >= 75)) {
        ctx.fillText(day(point.at), Math.min(width - 26, Math.max(26, x[i])), height - 8);
        lastLabel = x[i];
      }
    });
    if (selected >= 0) {
      ctx.strokeStyle = style.getPropertyValue('--muted').trim();
      ctx.setLineDash([3, 4]);
      ctx.beginPath();
      ctx.moveTo(x[selected], top);
      ctx.lineTo(x[selected], bottom);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    series.forEach((item, seriesIndex) => {
      ctx.lineWidth = 2;
      ctx.strokeStyle = colors[seriesIndex];
      ctx.fillStyle = colors[seriesIndex];
      ctx.beginPath();
      let drawing = false;
      points.forEach((point, i) => {
        const value = point[item.key];
        if (value == null) {
          drawing = false;
          return;
        }
        if (drawing) {
          if (opts.stepped) ctx.lineTo(x[i], y(points[i - 1][item.key]));
          ctx.lineTo(x[i], y(value));
        } else ctx.moveTo(x[i], y(value));
        drawing = true;
      });
      ctx.stroke();
      points.forEach((point, i) => {
        if (point[item.key] == null || (i !== selected && points.length > 12)) return;
        ctx.beginPath();
        ctx.arc(x[i], y(point[item.key]), i === selected ? 4 : 2.5, 0, Math.PI * 2);
        ctx.fill();
      });
    });
  }
  canvas.addEventListener('pointermove', event => {
    const relative = event.clientX - canvas.getBoundingClientRect().left;
    const index = x.reduce((nearest, candidate, i) =>
      Math.abs(candidate - relative) < Math.abs(x[nearest] - relative) ? i : nearest, 0);
    if (index === selected) return;
    selected = index;
    opts.preview?.(points[selected]);
    draw();
  });
  canvas.addEventListener('pointerleave', () => {
    selected = -1;
    opts.preview?.(null);
    draw();
  });
  if (opts.select) {
    canvas.style.cursor = 'pointer';
    canvas.addEventListener('click', () => { if (selected >= 0) opts.select(points[selected]); });
  }
  charts.set(canvas, draw);
  chartObserver.observe(canvas);
  return canvas;
}

function chartTable(headers, rows) {
  const details = element('details', '', 'chart-values');
  details.append(element('summary', t('chartValues')), table(headers, rows));
  return details;
}

function periodLabel(point) {
  return point.until - point.at === DAY ? day(point.at) : day(point.at) + ' – ' + day(point.until - 1);
}

function renderActivity(jobs) {
  $('activity-legend').replaceChildren();
  if (!state.history.length) {
    clearChart($('activity'), element('p', t('queueEmpty'), 'empty'));
    return;
  }
  const days = Number($('period').value);
  const anchor = Math.max(state.anchor, state.history.at(-1).at);
  const end = (Math.floor(anchor / DAY) + 1) * DAY;
  const start = end - days * DAY;
  const step = (days > 30 ? 7 : 1) * DAY;
  const series = [
    {key: 'active', label: t('active'), color: colors[0]},
    {key: 'added', label: t('added'), color: colors[1]},
    {key: 'updated', label: t('updatedSeries'), color: colors[2]}
  ];
  for (const item of series) {
    const key = element('span', '', 'legend-key');
    const dot = element('span', '', 'legend-dot');
    dot.style.setProperty('--series', 'var(' + item.color + ')');
    key.append(dot, item.label);
    $('activity-legend').append(key);
  }
  const activityChoices = countHistory(state, start, end, step, matches);
  if (selectedPeriod) selectedPeriod = activityChoices.find(point => point.at === selectedPeriod.at);
  const preview = element('p', '', 'activity-selection');
  const select = point => {
    selectedPeriod = point;
    visible = pageSize;
    renderPostings(jobs);
    location.hash = '/postings';
  };
  const plot = chart(activityChoices, series, {
    zero: true, select,
    preview: point => {
      preview.textContent = point ? [periodLabel(point), ...series.map(item =>
        item.label + ' ' + number(point[item.key]))].join(' · ') : '';
    }
  });
  const values = chartTable([t('date'), ...series.map(item => item.label)], activityChoices.map(point => [
    button(periodLabel(point), () => select(point)), ...series.map(item => number(point[item.key]))
  ]));
  clearChart($('activity'), plot, preview, values);
}

function renderPayComparison(jobs) {
  const groups = salaryComparisons(jobs);
  $('pay-comparison').replaceChildren();
  if (!groups.length) $('pay-comparison').append(element('p', t('noSalaryData'), 'empty'));
  for (const {currency, period, baseline, rows} of groups) {
    const block = element('div', '', 'pay-block');
    const columns = [t('company_size'), t('salaryMinimum') + ' · ' + unit(currency, period), t('sample'), t('difference')];
    const values = rows.map(({size, count, amount, delta}) => [
      t(size), amount == null ? '—' : number(amount), number(count),
      delta == null ? '—' : size === baseline ? t('baseline')
        : element('span', number(delta / 100, {style: 'percent', maximumFractionDigits: 1, signDisplay: 'exceptZero'}), 'delta')
    ]);
    block.append(table(columns, values));
    $('pay-comparison').append(block);
  }
}

function renderAnalytics(jobs) {
  bars($('bars'), rank(jobs, job => job.technologies ?? []), jobs.length);
  const field = $('group-by').value;
  bars($('distribution'), rank(jobs, job => [job[field] || t('unknown')]), jobs.length);
  renderPayComparison(jobs);
  renderActivity(jobs);
}

function render() {
  if (!state) return;
  const filtered = baseJobs.filter(matches);
  renderMetrics(filtered);
  renderChanges(filtered);
  if (activeScreen === 'analytics') renderAnalytics(filtered);
  renderPostings(filtered);
}

function renderSalaryHistory(container, job) {
  container.append(element('h3', t('salaryHistory')));
  const points = salaryHistory(state.history, job);
  const valid = points.filter(point => point.pay);
  const payKinds = new Set(valid.map(({pay}) => unit(pay.currency, pay.period)));
  if (valid.length < 2 || payKinds.size !== 1) {
    container.append(element('p', t('noHistory')));
  } else {
    const series = [{key: 'value', color: colors[0]}];
    const values = points.map(point => ({...point, value: point.pay?.amount ?? null}));
    const last = values.at(-1);
    if (last.value != null && job.lastSeen > last.at) {
      values.push({...last, at: job.lastSeen});
    }
    container.append(element('p', t('historyNote') + ' · ' + [...payKinds][0]), chart(values, series, {stepped: true}));
  }
  if (points.length) {
    container.append(chartTable([t('date'), t('salary')], points.map(point => [
      dateTime(point.at), point.job ? salary(point.job) : '—'
    ])));
  }
}

function detail(job) {
  selectedJob = job;
  const box = $('detail-content');
  const title = element('h2', job.title);
  title.id = 'detail-title';
  clearChart(box, element('div', job.site || '', 'eyebrow'), title,
    element('p', [job.company, job.location, job.seniority].filter(Boolean).join(' · ')));
  const data = element('dl', '', 'detail-data');
  const fields = [];
  if (timestamp(job.published_at) != null) fields.push(['publishedDate', dateTime(timestamp(job.published_at))]);
  fields.push(['salary', salary(job)], ['company_size', t(job.company_size)],
    ['company_headcount', job.company_headcount ? number(job.company_headcount) : '—'],
    ['firstSeen', dateTime(job.firstSeen)], ['lastSeen', dateTime(job.lastSeen)]);
  if (job.firstSeen !== job.versionAt) fields.push(['lastChanged', dateTime(job.versionAt)]);
  for (const [label, value] of fields) data.append(element('dt', t(label)), element('dd', value));
  box.append(data);
  const links = element('div', '', 'detail-links');
  for (const source of job.sources) {
    links.append(sourceLink(source, (dataset.dataset_kind === 'synthetic' ? t('demoLink') : t('sourceLink'))
      + ' · ' + (source.site || t('site'))));
  }
  box.append(links);
  renderSalaryHistory(box, job);
  const candidates = baseJobs.filter(candidate => candidate.key !== job.key
    && candidate.sources.some(source => job.possibleDuplicates.includes(source.key)));
  if (candidates.length) {
    box.append(element('h3', t('possibleDuplicates')));
    const list = element('ul');
    for (const candidate of candidates) {
      const item = element('li');
      item.append(button(candidate.title + ' · ' + candidate.company, () => detail(candidate)));
      list.append(item);
    }
    box.append(list);
  }
  for (const field of listFields) {
    if (!job[field]?.length) continue;
    const tags = element('div', '', 'tags');
    tags.append(...job[field].map(label => element('span', label, 'tag')));
    box.append(element('h3', t(field)), tags);
  }
  if (job.confidence != null || job.quality_issues?.length) {
    box.append(element('h3', t('quality')), element('p', t('confidence', {score: job.confidence ?? '—'})));
    const issues = element('ul');
    for (const issue of job.quality_issues ?? []) issues.append(element('li', issue));
    box.append(issues);
  }
  if (!$('detail').open) $('detail').showModal();
}

function renderMetadata() {
  $('dataset').textContent = t(dataset
    ? (dataset.dataset_kind === 'synthetic' ? 'synthetic' : 'published')
    : (loadError ? 'unavailable' : 'loading'));
  const notice = t(dataset?.dataset_kind === 'real' ? 'realNotice' : 'syntheticNotice');
  $('notice').textContent = [notice, loadError && dataset ? t('refreshError') : ''].filter(Boolean).join(' ');
  const publishedAt = timestamp(dataset?.generated_at);
  $('updated').textContent = publishedAt == null ? '' : t('updated') + ' ' + dateTime(publishedAt);
  $('checked').textContent = mockStatus === 'running' ? t('mockRunning') : mockStatus === 'failed' ? t('mockFailed')
    : state ? t('checked', {date: dateTime(state.checkedAt)}) : '';
  if (!dataset && loadError) {
    $('status').hidden = false;
    $('status').textContent = t('loadError', {error: loadError});
  }
}

function renderTheme() {
  const {theme, mode} = document.documentElement.dataset;
  for (const radio of $('theme-choices').querySelectorAll('input[name="theme"]')) {
    radio.checked = radio.value === theme;
  }
  $('mode-toggle').setAttribute('aria-pressed', String(mode === 'dark'));
  $('mode-label').textContent = t(mode);
  $('mode-icon').textContent = mode === 'dark' ? '☾' : '☀';
  for (const canvas of document.querySelectorAll('canvas')) charts.get(canvas)?.();
}

function menuExpanded(expanded) {
  if (expanded) filtersExpanded(false);
  $('sidebar').classList.toggle('is-expanded', expanded);
  $('menu-toggle').setAttribute('aria-expanded', String(expanded));
}

function filtersExpanded(expanded) {
  if (expanded) menuExpanded(false);
  $('sidebar').classList.toggle('filters-expanded', expanded);
  $('filter-toggle').setAttribute('aria-expanded', String(expanded));
}

function showScreen(focusHeading = false) {
  const route = location.hash.replace(/^#\/?/, '');
  const nextScreen = Object.hasOwn(routes, route) ? route : 'overview';
  if (activeScreen === nextScreen) return;
  activeScreen = nextScreen;
  const allowFilters = filterRoutes.has(activeScreen);
  $('filter-panel').hidden = $('filter-toggle').hidden = !allowFilters;
  for (const key of Object.keys(routes)) $('screen-' + key).hidden = key !== activeScreen;
  for (const link of $('app-nav').querySelectorAll('a[data-route]')) {
    if (link.dataset.route === activeScreen) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  menuExpanded(false);
  filtersExpanded(false);
  document.title = t(routes[activeScreen]) + ' · SkillMiner';
  if ($('detail').open) $('detail').close();
  window.scrollTo(0, 0);
  if (focusHeading) $(activeScreen + '-title').focus({preventScroll: true});
  if (activeScreen === 'analytics' && state) renderAnalytics(baseJobs.filter(matches));
}

function applyLanguage() {
  document.documentElement.lang = language;
  document.title = t(routes[activeScreen]) + ' · SkillMiner';
  $('language').value = language;
  document.querySelectorAll('[data-i18n]').forEach(node => { node.textContent = t(node.dataset.i18n); });
  document.querySelectorAll('[data-i18n-aria]').forEach(node => node.setAttribute('aria-label', t(node.dataset.i18nAria)));
  document.querySelectorAll('[data-i18n-placeholder]').forEach(node => node.setAttribute('placeholder', t(node.dataset.i18nPlaceholder)));
  renderTheme();
  render();
  renderMetadata();
  if ($('detail').open && selectedJob) detail(selectedJob);
}

function readHistory(key) {
  try {
    const previous = JSON.parse(readPreference(key));
    return previous && Array.isArray(previous.history) && previous.current ? previous : null;
  } catch {
    return null;
  }
}

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, {...options, cache: 'no-store'});
  if (!response.ok) throw new Error('HTTP ' + response.status);
  return response.json();
}

function showSnapshot(data, current) {
  dataset = data;
  state = current;
  baseJobs = canonicalJobs(Object.values(state.current));
  populateFilters();
  render();
}

function restoreSnapshot() {
  const kind = readPreference('skillminer-dataset-kind');
  if (!['synthetic', 'real'].includes(kind)) return;
  const previous = readHistory(statePrefix + kind);
  if (!previous) return;
  showSnapshot({dataset_kind: kind, generated_at: previous.generatedAt}, previous);
  renderMetadata();
}

async function refreshSnapshot(checkMock = true) {
  if (pending) return pending;
  pending = (async () => {
    try {
      const snapshot = await fetch('data/jobs.json', {cache: 'no-store'});
      if (!snapshot.ok) throw new Error('HTTP ' + snapshot.status);
      const data = await snapshot.json();
      if (!Array.isArray(data.jobs) || !['synthetic', 'real'].includes(data.dataset_kind)) {
        throw new Error(t('invalidData'));
      }
      const demo = data.dataset_kind === 'synthetic' ? await fetchJSON('data/demo.json') : null;
      const storageKey = statePrefix + data.dataset_kind;
      let previous = readHistory(storageKey) ?? (dataset?.dataset_kind === data.dataset_kind ? state : null);
      for (const archived of data.snapshot_history ?? []) {
        const at = timestamp(archived.generated_at);
        if (!Array.isArray(archived.jobs) || at == null || at <= (timestamp(previous?.generatedAt) ?? -Infinity)) continue;
        previous = reconcileSnapshot(archived, previous, demo, at);
        previous.generatedAt = archived.generated_at;
      }
      const at = data.snapshot_history ? (timestamp(data.generated_at) ?? Date.now()) : Date.now();
      const current = reconcileSnapshot(data, previous, demo, at);
      current.checkedAt = Date.now();
      current.generatedAt = data.generated_at;
      savePreference(storageKey, JSON.stringify(current));
      savePreference('skillminer-dataset-kind', data.dataset_kind);
      loadError = null;
      showSnapshot(data, current);
      return snapshot.headers.get('X-SkillMiner-Refresh') === 'mock';
    } catch (error) {
      loadError = error.message;
      return false;
    } finally {
      renderMetadata();
    }
  })();
  try {
    const supportsMock = await pending;
    if (checkMock && supportsMock) refreshMocks();
  } finally {
    pending = null;
  }
}

function refreshMocks() {
  if (mockRequest) return;
  mockRequest = (async () => {
    try {
      const initial = await fetchJSON('api/refresh', {method: 'POST'});
      mockStatus = initial.status;
      renderMetadata();
      if (mockStatus !== 'running') return;
      while (mockStatus === 'running' && !document.hidden) {
        await new Promise(resolve => setTimeout(resolve, 1500));
        mockStatus = (await fetchJSON('api/refresh')).status;
        renderMetadata();
      }
      if (mockStatus === 'ready') await refreshSnapshot(false);
    } catch {
      mockStatus = 'failed';
      renderMetadata();
    } finally {
      mockRequest = null;
    }
  })();
}

function csvCell(value) {
  let escaped = String(value ?? '');
  if (/^[=+\-@\t\r]/.test(escaped)) escaped = "'" + escaped;
  return '"' + escaped.replaceAll('"', '""') + '"';
}

$('export').onclick = () => {
  const fields = ['title', 'company', 'location', 'seniority', 'specialization', 'salary_min', 'salary_max',
    'salary_currency', 'company_headcount', 'company_size', 'low_confidence', 'source_url'];
  const rows = [fields, ...listedJobs.map(job => fields.map(field => job[field]))];
  const csv = '\uFEFF' + rows.map(row => row.map(csvCell).join(',')).join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], {type: 'text/csv;charset=utf-8'}));
  const link = element('a');
  link.href = url;
  link.download = 'skillminer.csv';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

function filterChanged() {
  visible = pageSize;
  selectedPeriod = null;
  render();
}

for (const id of ['search', ...filterFields, 'doubtful', 'duplicates']) {
  $(id).addEventListener('input', filterChanged);
}
$('reset').onclick = () => {
  for (const id of ['search', ...filterFields]) $(id).value = '';
  $('doubtful').checked = false;
  $('duplicates').checked = false;
  filterChanged();
};
$('period').onchange = filterChanged;
$('group-by').onchange = render;
$('more').onclick = () => {
  visible += pageSize;
  renderPostings(baseJobs.filter(matches));
};
$('close').onclick = () => $('detail').close();
$('detail').addEventListener('close', () => { clearChart($('detail-content')); selectedJob = null; });
$('detail').addEventListener('click', event => { if (event.target === $('detail')) $('detail').close(); });
$('language').onchange = () => {
  if (!Object.hasOwn(MESSAGES, $('language').value)) return;
  language = $('language').value;
  savePreference('skillminer-language', language);
  applyLanguage();
};
$('theme-choices').addEventListener('change', event => {
  const theme = event.target.value;
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.mode = preferredMode ?? (theme === 'zive' ? 'dark' : 'light');
  savePreference('skillminer-theme', theme);
  renderTheme();
});
$('mode-toggle').onclick = () => {
  preferredMode = document.documentElement.dataset.mode === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.mode = preferredMode;
  savePreference('skillminer-mode', preferredMode);
  renderTheme();
};
$('rows-per-page').onchange = event => {
  pageSize = Number(event.target.value);
  visible = pageSize;
  savePreference('skillminer-page-size', event.target.value);
  if (state) renderPostings(baseJobs.filter(matches));
};
$('default-period').onchange = event => {
  $('period').value = event.target.value;
  savePreference('skillminer-default-period', event.target.value);
  filterChanged();
};
$('menu-toggle').onclick = () => menuExpanded($('menu-toggle').getAttribute('aria-expanded') !== 'true');
$('filter-toggle').onclick = () => {
  const expanded = $('filter-toggle').getAttribute('aria-expanded') !== 'true';
  filtersExpanded(expanded);
  if (expanded) $('filter-close').focus({preventScroll: true});
};
$('filter-close').onclick = () => {
  filtersExpanded(false);
  $('filter-toggle').focus();
};
$('app-nav').addEventListener('click', event => {
  if (event.target.closest('a')) menuExpanded(false);
});
document.addEventListener('keydown', event => {
  if (event.key !== 'Escape' || $('detail').open) return;
  if ($('sidebar').classList.contains('filters-expanded')) {
    filtersExpanded(false);
    $('filter-toggle').focus();
  } else if ($('sidebar').classList.contains('is-expanded')) {
    menuExpanded(false);
    $('menu-toggle').focus();
  }
});

window.addEventListener('hashchange', () => showScreen(true));
window.addEventListener('pageshow', event => { if (event.persisted) refreshSnapshot(); });
document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshSnapshot(); });
showScreen();
applyLanguage();
restoreSnapshot();
refreshSnapshot();
