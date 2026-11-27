'use strict';

const AnalyticsFX = (() => {
  let snapshot = null;
  const ready = fetch('data/exchange-rates.json', {cache: 'no-store'}).then(response => {
    if (!response.ok) throw new Error('Missing exchange-rate snapshot');
    return response.json();
  }).then(data => {
    if (data.base !== 'EUR' || !/^\d{4}-\d{2}-\d{2}$/.test(data.date) || data.rates?.EUR !== 1) return;
    const rates = Object.fromEntries(Object.entries(data.rates).filter(([currency, rate]) =>
      /^[A-Z]{3}$/.test(currency) && typeof rate === 'number' && Number.isFinite(rate) && rate > 0));
    snapshot = {date: data.date, rates};
  }).catch(() => {});
  return {ready, rates: () => snapshot?.rates || {EUR: 1}, date: () => snapshot?.date || null};
})();
