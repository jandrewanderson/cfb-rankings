let currentTab = 'rankings';
let currentDataset = [];
let conferenceDataset = [];
let manifest = {};

async function init() {
  await loadManifest();
  await loadRankings();
}

async function loadManifest() {
  try {
    const res = await fetch('data/manifest.json');
    if (res.ok) {
      manifest = await res.json();
      updateWeekDropdown();
    }
  } catch (e) {
    console.warn("Could not load manifest.json", e);
  }
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
    loadConferences();
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
  loadRankings();
}

async function loadRankings() {
  const isMulti = document.getElementById('modeSelect').value === 'multi';
  let candidates = [];

  if (isMulti) {
    const range = document.getElementById('rangeSelect').value;
    candidates = [`data/multiyear/${range}.json`];
  } else {
    const yr = document.getElementById('seasonSelect').value;
    const wkVal = document.getElementById('weekSelect').value;
    
    candidates = [
      `data/${yr}/${wkVal}.json`,
      `data/${yr}/latest.json`,
      `data/latest.json`
    ];
  }

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
        <td colspan="19" class="p-8 text-center text-slate-400">
          <div class="text-rose-400 font-bold mb-2">Data not loaded directly from file URL</div>
          <div class="text-xs text-slate-500 max-w-md mx-auto">
            Run <code class="text-blue-400 font-mono bg-slate-800 px-2 py-0.5 rounded">python -m http.server 8000</code> in your terminal and open 
            <a href="http://localhost:8000" class="underline text-blue-400">http://localhost:8000</a>.
          </div>
        </td>
      </tr>
    `;
  }
}

async function loadConferences() {
  try {
    const res = await fetch('data/conferences.json');
    if (res.ok) {
      conferenceDataset = await res.json();
      renderConferencesTable();
      return;
    }
  } catch (e) {}
  renderConferencesTable();
}

function renderCurrentTable() {
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

  const thead = document.getElementById('tableHead');
  const tbody = document.getElementById('tableBody');
  const isMulti = document.getElementById('modeSelect').value === 'multi';

  if (isMulti) {
    thead.innerHTML = `
      <tr class="text-slate-400 border-b border-slate-800">
        <th class="p-4">Rank</th>
        <th class="p-4">Team</th>
        <th class="p-4">Multi-Yr Score</th>
        <th class="p-4">Record</th>
        <th class="p-4">Win %</th>
        <th class="p-4">Cumulative Elo</th>
        <th class="p-4">Conf</th>
        <th class="p-4">Nat'l Venue Rank</th>
        <th class="p-4">4-Yr Margin: Home / Away (Spread)</th>
        <th class="p-4">Home Elo (&delta;Home)</th>
        <th class="p-4">Away Elo (&delta;Away)</th>
      </tr>
    `;
    tbody.innerHTML = filtered.map(r => `
      <tr class="hover:bg-slate-800/40 transition-colors border-b border-slate-800/50">
        <td class="p-4 font-bold text-blue-400">#${r.rank}</td>
        <td class="p-4 font-extrabold text-white">${r.team}</td>
        <td class="p-4 font-bold text-emerald-400 font-mono">${r.full_score.toFixed(1)}</td>
        <td class="p-4 text-slate-300 font-mono">${r.record}</td>
        <td class="p-4 text-slate-400 font-mono">${r.win_pct}%</td>
        <td class="p-4 text-slate-400 font-mono">${r.pure_elo.toFixed(1)}</td>
        <td class="p-4 text-slate-300">${r.conf}</td>
        <td class="p-4 text-slate-400 font-mono">#${r.venue_rank}</td>
        <td class="p-4 text-slate-400 font-mono text-xs">${r.margin_str}</td>
        <td class="p-4 text-emerald-400 font-mono text-xs">${r.home_elo_str}</td>
        <td class="p-4 text-rose-400 font-mono text-xs">${r.away_elo_str}</td>
      </tr>
    `).join('');
  } else {
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
      </tr>
    `;
    tbody.innerHTML = filtered.map(r => `
      <tr class="hover:bg-slate-800/40 transition-colors border-b border-slate-800/50 text-xs">
        <td class="p-3 font-bold text-blue-400">#${r.rank}</td>
        <td class="p-3 font-extrabold text-emerald-400 font-mono">${r.full_score.toFixed(1)}</td>
        <td class="p-3 font-extrabold text-white text-sm">${r.team}</td>
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
        <td class="p-3 text-slate-300 font-mono">${r.score_w_prior.toFixed(1)}</td>
        <td class="p-3 text-slate-400 font-mono">#${r.pure_elo_rank}</td>
        <td class="p-3 text-slate-300 font-mono">${r.pure_elo.toFixed(1)}</td>
        <td class="p-3 text-slate-400 font-mono">#${r.venue_rank}</td>
        <td class="p-3 text-slate-400 font-mono text-[11px]">${r.margin_str}</td>
        <td class="p-3 text-emerald-400 font-mono text-[11px]">${r.home_elo_str}</td>
        <td class="p-3 text-rose-400 font-mono text-[11px]">${r.away_elo_str}</td>
      </tr>
    `).join('');
  }
}

function renderConferencesTable() {
  const thead = document.getElementById('tableHead');
  const tbody = document.getElementById('tableBody');
  const search = (document.getElementById('searchInput').value || '').toLowerCase();
  
  const filtered = conferenceDataset.filter(c => c.name.toLowerCase().includes(search));

  thead.innerHTML = `
    <tr class="text-slate-400 border-b border-slate-800 text-xs">
      <th class="p-4">Rank</th>
      <th class="p-4">Conference</th>
      <th class="p-4">4-Yr Base</th>
      <th class="p-4">3-Yr Base</th>
      <th class="p-4">2-Yr Base</th>
      <th class="p-4">1-Yr Base</th>
      <th class="p-4">&Delta; (4Yr &rarr; 1Yr)</th>
      <th class="p-4">1-Yr w/ Prior</th>
      <th class="p-4">Cur-Yr</th>
      <th class="p-4">&Delta; (Prior &rarr; Cur)</th>
      <th class="p-4">Weekly &Delta;</th>
    </tr>
  `;
  tbody.innerHTML = filtered.map(c => `
    <tr class="hover:bg-slate-800/40 transition-colors border-b border-slate-800/50">
      <td class="p-4 font-bold text-blue-400">#${c.rank}</td>
      <td class="p-4 font-extrabold text-white text-base">${c.name}</td>
      <td class="p-4 font-bold text-emerald-400 font-mono">${c.score_4yr.toFixed(1)}</td>
      <td class="p-4 text-slate-300 font-mono">${c.score_3yr.toFixed(1)}</td>
      <td class="p-4 text-slate-300 font-mono">${c.score_2yr.toFixed(1)}</td>
      <td class="p-4 text-slate-300 font-mono">${c.score_1yr.toFixed(1)}</td>
      <td class="p-4 font-mono font-bold ${c.delta_4yr_to_1yr >= 0 ? 'text-emerald-400' : 'text-rose-400'}">
        ${c.delta_4yr_to_1yr > 0 ? '+' + c.delta_4yr_to_1yr.toFixed(1) : c.delta_4yr_to_1yr.toFixed(1)}
      </td>
      <td class="p-4 text-slate-300 font-mono">${c.score_1yr_prior.toFixed(1)}</td>
      <td class="p-4 font-bold text-blue-400 font-mono">${c.score_cur.toFixed(1)}</td>
      <td class="p-4 font-mono font-bold ${c.delta_prior_to_cur >= 0 ? 'text-emerald-400' : 'text-rose-400'}">
        ${c.delta_prior_to_cur > 0 ? '+' + c.delta_prior_to_cur.toFixed(1) : c.delta_prior_to_cur.toFixed(1)}
      </td>
      <td class="p-4 font-mono ${c.delta_wk >= 0 ? 'text-emerald-400' : 'text-rose-400'}">
        ${c.delta_wk > 0 ? '+' + c.delta_wk.toFixed(1) : c.delta_wk.toFixed(1)}
      </td>
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
      <th class="p-4">Home Boost (&delta;Home)</th>
      <th class="p-4">Away Penalty (&delta;Away)</th>
      <th class="p-4">4-Yr Spread</th>
      <th class="p-4">Host Edge</th>
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

init();