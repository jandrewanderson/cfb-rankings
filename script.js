let currentTab = 'rankings';
let currentDataset = [];
let conferenceDataset = [];
let yearlyIndex = {};
let manifest = {};

async function init() {
  await loadManifest();
  await loadYearlyIndex();
  await loadRankings();
}

async function loadManifest() {
  try {
    // Append timestamp to force cache bypass
    const t = new Date().getTime();
    const res = await fetch(`data/manifest.json?t=${t}`);
    if (res.ok) {
      manifest = await res.json();
      updateWeekDropdown();
    }
  } catch (e) {
    console.warn("Could not load manifest.json", e);
  }
}

async function loadYearlyIndex() {
  try {
    // Append timestamp to force cache bypass
    const t = new Date().getTime();
    const res = await fetch(`data/yearly_index.json?t=${t}`);
    if (res.ok) {
      yearlyIndex = await res.json();
      populateEraSelectors();
    }
  } catch (e) {
    console.warn("Could not load yearly_index.json", e);
  }
}

function populateEraSelectors() {
  const startSel = document.getElementById('startYearSelect');
  const endSel = document.getElementById('endYearSelect');
  if (!startSel || !endSel) return;

  const sampleTeam = Object.keys(yearlyIndex)[0];
  if (!sampleTeam) return;

  const years = Object.keys(yearlyIndex[sampleTeam]).map(Number).sort((a, b) => a - b);
  if (years.length === 0) return;
  
  const minYear = years[0];
  const maxYear = years[years.length - 1];

  startSel.innerHTML = '';
  endSel.innerHTML = '';

  years.forEach(y => {
    startSel.innerHTML += `<option value="${y}" ${y === Math.max(minYear, maxYear - 4) ? 'selected' : ''}>${y}</option>`;
    endSel.innerHTML += `<option value="${y}" ${y === maxYear ? 'selected' : ''}>${y}</option>`;
  });
}

function updateWeekDropdown() {
  const yr = document.getElementById('seasonSelect').value;
  const weekSelect = document.getElementById('weekSelect');
  const weeks = manifest[yr] || [1, 2, 3, 4, 5, 6];

  weekSelect.innerHTML = '<option value="latest" selected>Latest</option>';
  weeks.forEach(w => {
    weekSelect.innerHTML += `<option value="week_${w}">Week ${w}</option>`;
  });
}

function onSeasonChange() {
  updateWeekDropdown();
  loadRankings();
}

function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll('nav button').forEach(b => {
    b.className = 'px-4 py-2 rounded-md font-semibold text-sm text-slate-400 hover:text-white transition-colors';
  });
  const activeBtn = document.getElementById(`tab-${tab}`);
  if (activeBtn) activeBtn.className = 'px-4 py-2 rounded-md font-semibold text-sm bg-blue-600 text-white shadow-lg shadow-blue-600/30';
  
  const searchBox = document.getElementById('searchInput');
  if (tab === 'conferences') {
    searchBox.placeholder = "Search conference...";
    renderConferencesTable();
  } else if (tab === 'venues') {
    searchBox.placeholder = "Search venue or team...";
    renderVenuesTable();
  } else {
    searchBox.placeholder = "Search team or conference...";
    loadRankings();
  }
}

function onModeChange() {
  const isMulti = document.getElementById('modeSelect').value === 'multi';
  document.getElementById('seasonContainer').classList.toggle('hidden', isMulti);
  document.getElementById('weekContainer').classList.toggle('hidden', isMulti);
  document.getElementById('rangeContainer').classList.toggle('hidden', !isMulti);
  document.getElementById('priorBadgeContainer').classList.toggle('hidden', isMulti);

  if (isMulti) {
    renderEraView();
  } else {
    loadRankings();
  }
}

async function loadRankings() {
  const yr = document.getElementById('seasonSelect').value;
  const wkVal = document.getElementById('weekSelect').value;
  
  // Unique timestamp to break CDN caching
  const t = new Date().getTime();
  
  const candidates = [
    `data/${yr}/${wkVal}.json?t=${t}`,
    `data/${yr}/latest.json?t=${t}`,
    `data/latest.json?t=${t}`
  ];

  let loaded = false;
  for (const path of candidates) {
    try {
      const res = await fetch(path);
      if (res.ok) {
        currentDataset = await res.json();
        renderCurrentTable();
        loaded = true;
        break;
      }
    } catch (e) {}
  }

  if (!loaded) {
    document.getElementById('tableBody').innerHTML = `
      <tr>
        <td colspan="22" class="p-8 text-center text-slate-400">
          <div class="text-rose-400 font-bold mb-2">Dataset not loaded</div>
          <div class="text-xs text-slate-500">Run python build_data.py to generate data.</div>
        </td>
      </tr>
    `;
  }
}

function renderEraView() {
  const startYear = parseInt(document.getElementById('startYearSelect').value, 10);
  const endYear = parseInt(document.getElementById('endYearSelect').value, 10);
  const search = (document.getElementById('searchInput').value || '').toLowerCase();

  if (startYear > endYear) {
    alert("Start Year cannot be greater than End Year.");
    return;
  }

  const eraData = [];
  for (const [team, history] of Object.entries(yearlyIndex)) {
    let scoreSum = 0;
    let sosSum = 0;
    let totalWins = 0;
    let totalLosses = 0;
    let count = 0;
    let peakScore = -1;
    let peakYear = null;
    let lowScore = 9999;
    let lowYear = null;

    for (let y = startYear; y <= endYear; y++) {
      const yearStat = history[String(y)];
      if (yearStat) {
        scoreSum += yearStat.score;
        sosSum += yearStat.sos;
        totalWins += yearStat.w;
        totalLosses += yearStat.l;
        count++;

        if (yearStat.score > peakScore) {
          peakScore = yearStat.score;
          peakYear = y;
        }
        if (yearStat.score < lowScore) {
          lowScore = yearStat.score;
          lowYear = y;
        }
      }
    }

    if (count > 0) {
      const avgScore = scoreSum / count;
      const avgSos = sosSum / count;
      const totalGames = totalWins + totalLosses;
      const winPct = totalGames > 0 ? (totalWins / totalGames) * 100.0 : 0.0;

      eraData.push({
        team,
        avg_score: roundNum(avgScore, 1),
        cumulative_record: `${totalWins}–${totalLosses}`,
        win_pct: roundNum(winPct, 1),
        avg_sos: roundNum(avgSos, 1),
        peak_str: `${peakYear} (${peakScore.toFixed(1)})`,
        low_str: `${lowYear} (${lowScore.toFixed(1)})`,
        seasons_in_window: `${count} / ${endYear - startYear + 1}`
      });
    }
  }

  eraData.sort((a, b) => b.avg_score - a.avg_score);
  eraData.forEach((row, i) => row.rank = i + 1);

  currentDataset = eraData;

  const thead = document.getElementById('tableHead');
  const tbody = document.getElementById('tableBody');
  const filtered = eraData.filter(d => d.team.toLowerCase().includes(search));

  thead.innerHTML = `
    <tr class="text-slate-400 border-b border-slate-800 text-xs">
      <th class="p-4">Rank</th>
      <th class="p-4">Team</th>
      <th class="p-4">Era Avg Score</th>
      <th class="p-4">Cumulative Record</th>
      <th class="p-4">Win %</th>
      <th class="p-4">Era Avg SOS</th>
      <th class="p-4">Peak Season</th>
      <th class="p-4">Lowest Season</th>
      <th class="p-4">Seasons Sampled</th>
    </tr>
  `;

  tbody.innerHTML = filtered.map(r => `
    <tr class="hover:bg-slate-800/40 transition-colors border-b border-slate-800/50">
      <td class="p-4 font-bold text-blue-400">#${r.rank}</td>
      <td class="p-4 font-extrabold text-white text-base">${r.team}</td>
      <td class="p-4 font-extrabold text-emerald-400 font-mono text-base">${r.avg_score.toFixed(1)}</td>
      <td class="p-4 text-slate-200 font-mono">${r.cumulative_record}</td>
      <td class="p-4 text-slate-400 font-mono">${r.win_pct}%</td>
      <td class="p-4 text-slate-300 font-mono">${r.avg_sos.toFixed(1)}</td>
      <td class="p-4 text-emerald-400/90 font-mono text-xs">${r.peak_str}</td>
      <td class="p-4 text-rose-400/90 font-mono text-xs">${r.low_str}</td>
      <td class="p-4 text-slate-500 font-mono text-xs">${r.seasons_in_window}</td>
    </tr>
  `).join('');
}

function renderCurrentTable() {
  const isMulti = document.getElementById('modeSelect').value === 'multi';
  if (isMulti) {
    renderEraView();
    return;
  }
  if (currentTab === 'conferences') {
    renderConferencesTable();
    return;
  }
  if (currentTab === 'venues') {
    renderVenuesTable();
    return;
  }

  const search = (document.getElementById('searchInput').value || '').toLowerCase();
  const filtered = currentDataset.filter(d => 
    (d.team && d.team.toLowerCase().includes(search)) || 
    (d.conf && d.conf.toLowerCase().includes(search))
  );

  const badge = document.getElementById('priorWeightBadge');
  if (filtered.length > 0 && filtered[0].w_prior_pct !== undefined) {
    badge.textContent = `Active Prior Weight: ${filtered[0].w_prior_pct}%`;
  } else {
    badge.textContent = `Active Prior Weight: --%`;
  }

  const thead = document.getElementById('tableHead');
  const tbody = document.getElementById('tableBody');

  thead.innerHTML = `
    <tr class="text-slate-400 border-b border-slate-800 text-[11px]">
      <th class="p-3">Rank (134)</th>
      <th class="p-3">Full Score</th>
      <th class="p-3">Team</th>
      <th class="p-3">Record</th>
      <th class="p-3">AP Rank</th>
      <th class="p-3">Delta Wk</th>
      <th class="p-3">SOS (Rank)</th>
      <th class="p-3">Conf</th>
      <th class="p-3">Conf 4-Yr</th>
      <th class="p-3">Conf 1-Yr w/ Prior</th>
      <th class="p-3">Conf Cur-Yr</th>
      <th class="p-3">Prior Rank</th>
      <th class="p-3">Score w/ Prior</th>
      <th class="p-3">Pure Rank</th>
      <th class="p-3">Pure Elo</th>
      <th class="p-3">Venue Rank</th>
      <th class="p-3">4-Yr Avg Margin (Spread)</th>
      <th class="p-3">Home Elo (&delta;Home)</th>
      <th class="p-3">Away Elo (&delta;Away)</th>
      <th class="p-3 text-slate-500">Prev Raw Elo</th>
      <th class="p-3 text-slate-500">Reg Rate ($R_i$)</th>
      <th class="p-3 text-slate-500">Prior Shift (&Delta;)</th>
    </tr>
  `;

  tbody.innerHTML = filtered.map(r => {
    const oppsTitle = r.opponents && r.opponents.length > 0 
      ? `Opponents played: ${r.opponents.join(', ')}` 
      : 'No opponents played yet';

    return `
      <tr class="hover:bg-slate-800/40 transition-colors border-b border-slate-800/50 text-xs">
        <td class="p-3 font-bold text-blue-400">#${r.rank}</td>
        <td class="p-3 font-extrabold text-emerald-400 font-mono text-sm">${r.full_score.toFixed(1)}</td>
        <td class="p-3 font-extrabold text-white text-sm" title="${oppsTitle}">
          ${r.team}
        </td>
        <td class="p-3 text-slate-200 font-mono">${r.record}</td>
        <td class="p-3 text-slate-400 font-mono">${r.ap_rank !== '-' ? '#' + r.ap_rank : '-'}</td>
        <td class="p-3 font-mono font-semibold ${r.delta_wk > 0 ? 'text-emerald-400' : (r.delta_wk < 0 ? 'text-rose-400' : 'text-slate-400')}">
          ${r.delta_wk > 0 ? '+' + r.delta_wk.toFixed(1) : r.delta_wk.toFixed(1)}
        </td>
        <td class="p-3 text-slate-400 font-mono">${r.sos.toFixed(1)} <span class="text-[10px] text-slate-500">(#${r.sos_rank})</span></td>
        <td class="p-3 text-slate-300 font-semibold">${r.conf}</td>
        <td class="p-3 text-slate-400 font-mono">${r.conf_4yr.toFixed(1)}</td>
        <td class="p-3 text-slate-400 font-mono">${r.conf_1yr_prior.toFixed(1)}</td>
        <td class="p-3 text-slate-400 font-mono">${r.conf_cur.toFixed(1)}</td>
        <td class="p-3 text-slate-400 font-mono">#${r.score_w_prior_rank}</td>
        <td class="p-3 text-blue-400 font-mono font-bold">${r.score_w_prior.toFixed(1)}</td>
        <td class="p-3 text-slate-400 font-mono">#${r.pure_elo_rank}</td>
        <td class="p-3 text-emerald-400 font-mono font-bold">${r.pure_elo.toFixed(1)}</td>
        <td class="p-3 text-slate-400 font-mono">#${r.venue_rank}</td>
        <td class="p-3 text-slate-400 font-mono text-[11px]">${r.margin_str}</td>
        <td class="p-3 text-emerald-400 font-mono text-[11px]">${r.home_elo_str}</td>
        <td class="p-3 text-rose-400 font-mono text-[11px]">${r.away_elo_str}</td>
        <td class="p-3 text-slate-500 font-mono text-[11px]">${r.prev_raw_elo ? r.prev_raw_elo.toFixed(1) : '-'}</td>
        <td class="p-3 text-slate-500 font-mono text-[11px]">${r.reg_rate_pct ? r.reg_rate_pct.toFixed(1) + '%' : '-'}</td>
        <td class="p-3 font-mono text-[11px] ${r.prior_shift > 0 ? 'text-emerald-500' : 'text-rose-500'}">
          ${r.prior_shift ? (r.prior_shift > 0 ? '+' + r.prior_shift.toFixed(1) : r.prior_shift.toFixed(1)) : '-'}
        </td>
      </tr>
    `;
  }).join('');
}

function renderConferencesTable() {
  const thead = document.getElementById('tableHead');
  const tbody = document.getElementById('tableBody');
  const search = (document.getElementById('searchInput').value || '').toLowerCase();
  
  const confMap = {};
  currentDataset.forEach(d => {
    if (!confMap[d.conf]) confMap[d.conf] = { count: 0, eloSum: 0, scoreSum: 0 };
    confMap[d.conf].count++;
    confMap[d.conf].eloSum += d.pure_elo;
    confMap[d.conf].scoreSum += d.full_score;
  });

  const confList = Object.keys(confMap).map(c => ({
    name: c,
    avg_elo: confMap[c].eloSum / confMap[c].count,
    avg_score: confMap[c].scoreSum / confMap[c].count,
    teams: confMap[c].count
  })).sort((a, b) => b.avg_score - a.avg_score);

  thead.innerHTML = `
    <tr class="text-slate-400 border-b border-slate-800 text-xs">
      <th class="p-4">Rank</th>
      <th class="p-4">Conference</th>
      <th class="p-4">Avg Full Score</th>
      <th class="p-4">Avg Pure Elo</th>
      <th class="p-4">FBS Programs</th>
    </tr>
  `;

  tbody.innerHTML = confList.filter(c => c.name.toLowerCase().includes(search)).map((c, i) => `
    <tr class="hover:bg-slate-800/40 transition-colors border-b border-slate-800/50">
      <td class="p-4 font-bold text-blue-400">#${i + 1}</td>
      <td class="p-4 font-extrabold text-white text-base">${c.name}</td>
      <td class="p-4 font-bold text-emerald-400 font-mono">${c.avg_score.toFixed(1)}</td>
      <td class="p-4 text-slate-300 font-mono">${c.avg_elo.toFixed(1)}</td>
      <td class="p-4 text-slate-500 font-mono">${c.teams}</td>
    </tr>
  `).join('');
}

function renderVenuesTable() {
  const thead = document.getElementById('tableHead');
  const tbody = document.getElementById('tableBody');
  const search = (document.getElementById('searchInput').value || '').toLowerCase();
  
  const venueList = currentDataset.filter(d => d.venue_rank !== undefined && 
    (d.team.toLowerCase().includes(search) || d.conf.toLowerCase().includes(search)))
    .sort((a, b) => a.venue_rank - b.venue_rank);

  thead.innerHTML = `
    <tr class="text-slate-400 border-b border-slate-800 text-xs">
      <th class="p-4">Venue Rank</th>
      <th class="p-4">Team</th>
      <th class="p-4">Conference</th>
      <th class="p-4">Home Crowd Boost (&delta;Home)</th>
      <th class="p-4">Road Travel Penalty (&delta;Away)</th>
      <th class="p-4">4-Yr Spread (Home - Away)</th>
      <th class="p-4">Total Stadium Edge</th>
    </tr>
  `;
  tbody.innerHTML = venueList.map(v => `
    <tr class="hover:bg-slate-800/40 transition-colors border-b border-slate-800/50">
      <td class="p-4 font-bold text-blue-400">#${v.venue_rank}</td>
      <td class="p-4 font-extrabold text-white">${v.team}</td>
      <td class="p-4 text-slate-300">${v.conf}</td>
      <td class="p-4 text-emerald-400 font-mono">+${v.d_h.toFixed(1)}</td>
      <td class="p-4 text-rose-400 font-mono">${v.d_a.toFixed(1)}</td>
      <td class="p-4 text-slate-300 font-mono">${v.spread > 0 ? '+' + v.spread.toFixed(1) : v.spread.toFixed(1)} pts</td>
      <td class="p-4 font-bold text-white font-mono">+${(v.d_h + 16.0).toFixed(1)}</td>
    </tr>
  `).join('');
}

function exportCurrentTable(format) {
  if (format === 'pdf') {
    window.print();
    return;
  }
  if (!currentDataset || currentDataset.length === 0) {
    alert("No active data to export.");
    return;
  }
  const isMulti = document.getElementById('modeSelect').value === 'multi';
  const filename = isMulti 
    ? `cfb_era_${document.getElementById('startYearSelect').value}_${document.getElementById('endYearSelect').value}`
    : `cfb_rankings_${document.getElementById('seasonSelect').value}_${document.getElementById('weekSelect').value}`;

  if (format === 'json') {
    const blob = new Blob([JSON.stringify(currentDataset, null, 2)], { type: 'application/json' });
    downloadBlob(blob, `${filename}.json`);
  } else if (format === 'csv') {
    const keys = Object.keys(currentDataset[0]);
    const csvRows = [
      keys.join(','),
      ...currentDataset.map(row => keys.map(k => {
        let val = row[k];
        if (Array.isArray(val)) val = val.join('; ');
        return `"${String(val ?? '').replace(/"/g, '""')}"`;
      }).join(','))
    ];
    const blob = new Blob([csvRows.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
    downloadBlob(blob, `${filename}.csv`);
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function roundNum(val, dec) {
  return Number(Math.round(val + 'e' + dec) + 'e-' + dec);
}

init();