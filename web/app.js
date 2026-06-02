const $ = (id) => document.querySelector(id);
const state = {
  table: null,
  botTimer: null,
  revealTimer: null,
  stageKey: null,
  thinking: false,
  reveal: null,
};

const ACTION_LABELS = { fold: 'Fold', check: 'Check', call: 'Call', bet: 'Bet', raise: 'Raise' };
const STREET_LABELS = { preflop: 'PREFLOP', flop: 'FLOP', turn: 'TURN', river: 'RIVER', showdown: 'SHOWDOWN', winner: 'WINNER' };
const SUITS = { S: '♠', H: '♥', D: '♦', C: '♣' };

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'content-type': 'application/json' },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'request failed');
  return data;
}

function setTable(table) {
  const stageKey = `${table.id}:${table.hand_no}:${table.stage}`;
  const stageChanged = stageKey !== state.stageKey;
  state.table = table;
  if (stageChanged) {
    state.stageKey = stageKey;
    announceStreet(table.stage);
    table.stage === 'showdown' ? startShowdownReveal(table) : stopShowdownReveal();
  }
  render();
  scheduleBot();
}

async function createTable() {
  resetBotTimer();
  setTable(await api('/api/tables', { method: 'POST', body: { players: +$('#seats').value } }));
}

async function startNewHand() {
  resetBotTimer();
  setTable(await api(`/api/tables/${state.table.id}/new-hand`, { method: 'POST' }));
}

async function humanAct(action) {
  const amount = ['bet', 'raise'].includes(action) ? Number($('#betAmount')?.value || state.table.big_blind) : 0;
  setTable(await api(`/api/tables/${state.table.id}/action`, {
    method: 'POST',
    body: { player_id: state.table.current_player_id, action, amount },
  }));
}

async function botAct() {
  const table = state.table;
  if (!table || table.stage === 'showdown' || currentPlayer()?.is_human) return;
  state.thinking = false;
  setTable(await api(`/api/tables/${table.id}/bot-action`, { method: 'POST' }));
}

function scheduleBot() {
  resetBotTimer();
  if (!state.table || state.table.stage === 'showdown' || currentPlayer()?.is_human) return;
  state.thinking = true;
  render();
  state.botTimer = setTimeout(() => botAct().catch(showError), state.table.bot_delay_ms || 1000);
}

function resetBotTimer() {
  clearTimeout(state.botTimer);
  state.thinking = false;
}

function stopShowdownReveal() {
  clearTimeout(state.revealTimer);
  state.reveal = null;
}

function startShowdownReveal(table) {
  stopShowdownReveal();
  const order = (table.showdown || []).map((row) => row.player_id);
  const foldedWin = table.players.filter((p) => !p.folded).length <= 1;
  state.reveal = { key: `${table.id}:${table.hand_no}`, order, index: foldedWin ? order.length : 0, done: foldedWin || !order.length };
  if (!state.reveal.done) advanceShowdownReveal();
}

function advanceShowdownReveal() {
  const delay = currentRevealResult()?.reveal_ms || 1400;
  state.revealTimer = setTimeout(() => {
    if (!state.reveal || state.table?.stage !== 'showdown') return;
    state.reveal.index += 1;
    state.reveal.done = state.reveal.index >= state.reveal.order.length;
    render();
    state.reveal.done ? announceStreet('winner') : advanceShowdownReveal();
  }, 850);
}

function announceStreet(stage) {
  const banner = $('#streetBanner');
  banner.textContent = STREET_LABELS[stage] || stage.toUpperCase();
  banner.className = `street-banner show ${stage}`;
  clearTimeout(banner._timer);
  banner._timer = setTimeout(() => banner.classList.remove('show'), 1500);
}

function currentPlayer() { return state.table?.players[state.table.current_player]; }
function humanPlayer() { return state.table?.players.find((p) => p.is_human) || state.table?.players[0]; }
function escapeHtml(text) { return String(text).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
function revealDone() { return state.table?.stage !== 'showdown' || !state.reveal || state.reveal.done; }
function revealing() { return state.table?.stage === 'showdown' && state.reveal && !state.reveal.done; }
function playerRevealed(player) {
  if (state.table?.stage !== 'showdown') return false;
  if (player.folded) return false;
  if (revealDone()) return true;
  return state.reveal.order.slice(0, state.reveal.index).includes(player.id);
}

function cardHTML(card, cls = '') {
  if (!card || card === '??') return `<div class="card back ${cls}"><span>?</span><span class="bottom">?</span></div>`;
  const suit = card[1];
  const red = ['H', 'D'].includes(suit) ? 'red' : '';
  const label = `${card[0]}${SUITS[suit] || ''}`;
  return `<div class="card ${red} ${cls}"><span>${label}</span><span class="bottom">${label}</span></div>`;
}

function boardHTML() {
  const cards = state.table.board.map((c) => cardHTML(c));
  while (cards.length < 5) cards.push('<div class="card slot"></div>');
  return cards.join('');
}

function statGrid(player) {
  const table = state.table;
  const toCall = Math.max(0, table.current_bet - (player?.bet || 0));
  return `<div class="bet-grid">
    ${statBox('Stack', player?.chips ?? 0)}${statBox('Bet', player?.bet ?? 0)}
    ${statBox('To call', toCall)}${statBox('Total pot', table.pot)}
  </div>`;
}

function opponentStats(player) {
  const toCall = Math.max(0, state.table.current_bet - (player?.bet || 0));
  return `<div class="seat-stats">
    <span>Stack <b>${player?.chips ?? 0}</b></span>
    <span>Bet <b>${player?.bet ?? 0}</b></span>
    <span>Call <b>${toCall}</b></span>
  </div>`;
}

function statBox(label, value) { return `<span class="chipbox">${label}<b>${value}</b></span>`; }
function botClass(index) { return `bot-${(index % 5) + 1}`; }
function winnerNames() { return state.table.players.filter((p) => state.table.winner_ids.includes(p.id)).map((p) => p.name).join(', ') || 'Showdown'; }
function winnerStatus() {
  const names = winnerNames();
  return names === 'You' ? 'You win' : `${names} wins`;
}
function nextRevealName() {
  const id = state.reveal?.order[state.reveal.index];
  return state.table?.players.find((p) => p.id === id)?.name || 'winner';
}
function playerResult(player) { return state.table?.showdown?.find((row) => row.player_id === player?.id); }
function visibleResult(player) { return playerRevealed(player) ? playerResult(player) : null; }
function currentRevealResult() {
  const id = state.reveal?.order[state.reveal.index];
  return state.table?.showdown?.find((row) => row.player_id === id);
}
function tierClass(result) { return result ? `tier-${result.tier}` : ''; }
function fmtSeconds(ms) { return `${(ms / 1000).toFixed(1)}s`; }

function render() {
  const table = state.table;
  if (!table) return;
  const actor = currentPlayer() || {};
  const human = humanPlayer();

  $('#pot').innerHTML = `<div>Pot ${table.pot}</div><small>Current bet ${table.current_bet}</small>`;
  $('#board').innerHTML = boardHTML();
  $('#yourHand').innerHTML = (human?.hand || []).map((c) => cardHTML(c)).join('') || cardHTML(null) + cardHTML(null);
  $('#heroStats').innerHTML = statGrid(human);
  $('#opponents').innerHTML = table.players.filter((p) => !p.is_human).map(opponentHTML).join('');
  $('#actionPanel').classList.toggle('active-turn', table.stage !== 'showdown');
  const heroResult = visibleResult(human);
  $('.hand-panel').className = `panel hand-panel ${tierClass(heroResult)} ${revealDone() && table.winner_ids.includes(human?.id) ? 'winner' : ''}`;
  $('#heroMadeHand').innerHTML = madeHandHTML(heroResult);
  $('#status').textContent = statusText(actor);
  $('#substatus').textContent = substatusText(table);
  $('#actions').innerHTML = actionsHTML(actor);
  $('#newHand').disabled = table.stage !== 'showdown' || revealing();
  $('#log').innerHTML = (table.action_log || []).slice().reverse().slice(0, 9).map((x) => `<div>· ${escapeHtml(x)}</div>`).join('');
  $('#raw').textContent = JSON.stringify(table, null, 2);
}

function statusText(actor) {
  if (revealing()) return `Showdown · revealing ${nextRevealName()}...`;
  if (state.table.stage === 'showdown') return winnerStatus();
  if (state.thinking && !actor.is_human) return `${actor.name} thinking...`;
  return `${actor.name || '-'} turn`;
}

function substatusText(table) {
  if (revealing()) {
    const result = currentRevealResult();
    const hand = result ? `${result.label} · ${fmtSeconds(result.reveal_ms)}` : 'revealing';
    return `Players reveal completed hands one by one · ${hand}.`;
  }
  return `${table.stage.toUpperCase()} · current bet ${table.current_bet} · ${table.message}`;
}

function opponentHTML(player, index) {
  const table = state.table;
  const active = player.id === table.current_player_id && table.stage !== 'showdown';
  const winner = revealDone() && table.winner_ids.includes(player.id);
  const result = visibleResult(player);
  const thought = active && state.thinking ? `thinking…` : active ? 'my turn' : '';
  const cue = table.last_action?.player_id === player.id
    ? `<div class="speech">${escapeHtml(table.last_action.speech)}</div>`
    : `<div class="think">${thought}</div>`;
  return `<div class="seat seat-${index} ${active ? 'active' : ''} ${winner ? 'winner' : ''} ${tierClass(result)} ${player.folded ? 'folded' : ''}">
    ${cue}
    <div class="seat-card">
      <div class="avatar-img ${botClass(index)}" role="img" aria-label="${escapeHtml(player.name)} avatar"></div>
      <div class="nameplate"><b>${escapeHtml(player.name)}</b>${winner ? ' · winner' : ''}${player.folded ? ' · folded' : ''}${opponentStats(player)}${opponentHandHTML(player)}</div>
    </div>
  </div>`;
}

function opponentHandHTML(player) {
  if (player.folded) return '<div class="seat-hole-cards muted">folded</div>';
  const cards = playerRevealed(player) ? player.hand : ['??', '??'];
  return `<div class="seat-hole-cards">${cards.map((c) => cardHTML(c, 'small')).join('')}</div>${madeHandHTML(visibleResult(player))}`;
}

function madeHandHTML(result) {
  return result ? `<div class="made-hand ${tierClass(result)}">${escapeHtml(result.label)}</div>` : '<div class="made-hand"></div>';
}

function actionsHTML(actor) {
  const table = state.table;
  if (revealing()) return '<button disabled>Revealing hands...</button>';
  if (table.stage === 'showdown') return '<button onclick="startNewHand()">Next Hand</button>';
  if (!actor.is_human) return `<button disabled>AI thinking ${fmtSeconds(table.bot_delay_ms)}...</button>`;
  const buttons = table.legal_actions.filter((a) => a !== 'new-hand').map((a) => `<button onclick="humanAct('${a}')">${ACTION_LABELS[a] || a}</button>`).join('');
  return `${buttons}${table.legal_actions.some((a) => ['bet', 'raise'].includes(a)) ? `<input id="betAmount" type="number" min="${table.big_blind}" value="${table.big_blind}" />` : ''}`;
}

function showError(error) {
  state.thinking = false;
  $('#status').textContent = error.message;
}

$('#create').onclick = createTable;
$('#newHand').onclick = startNewHand;
createTable().catch(showError);
