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
  
  // 변경된 고도화 실력/난이도 측정 통합 패널 업데이트 실행
  renderPlayerAnalysisSidePanel(table);
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

// [고도화 업데이트 완료] 실시간 실력측정 및 AI 난이도 연동 전용 대시보드 렌더러
function renderPlayerAnalysisSidePanel(table) {
  const target = $('#analysisPanel');
  if (!target) return;

  const styleMap = { 
    NORMAL: { text: '보통형 (Normal) 😐', color: '#10b981' }, 
    AGGRESSIVE: { text: '공격형 (Aggressive) 🔥', color: '#ef4444' }, 
    PASSIVE: { text: '수동형 (Passive) 🛡️', color: '#3b82f6' } 
  };
  const style = styleMap[table.analyzed_player_style] || { text: '분석 진행 중 🔍', color: '#a1a1aa' };

  // AI 난이도 시스템 정보 매핑
  const diffData = table.ai_difficulty_state || { score: 0.5, level: 'MEDIUM', label: '측정 중 (기본값)' };
  let diffColor = '#f59e0b'; // Medium 황색
  if (diffData.level === 'HARD') diffColor = '#dc2626'; // Hard 적색
  if (diffData.level === 'EASY') diffColor = '#3b82f6'; // Easy 청색

  // 이전 판까지의 누적 전적 데이터 정산
  const displayedTotalHands = Math.max(0, table.user_total_hands - 1);
  const winCount = table.user_win_count || 0;
  const winRatePercent = displayedTotalHands > 0 ? ((winCount / displayedTotalHands) * 100).toFixed(0) : 0;

  target.innerHTML = `
    <div style="border: 2px solid ${diffColor}; padding: 15px; border-radius: 8px; background-color: #1e1e1e; color: #fff; font-family: sans-serif; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
      <h3 style="margin-top: 0; color: #e5e7eb; font-size: 15px; border-bottom: 1px solid #3f3f46; padding-bottom: 8px; font-weight: bold;">📊 유저 분석 및 AI 난이도 시스템</h3>
      
      <div style="margin: 12px 0; padding-bottom: 10px; border-bottom: 1px dashed #3f3f46;">
        <span style="font-size: 11px; color: #a1a1aa; display: block; margin-bottom: 2px;">시스템 판단 AI 적용 난이도</span>
        <strong style="font-size: 16px; color: ${diffColor};">${diffData.label}</strong>
        <div style="font-size: 12px; color: #d4d4d8; margin-top: 4px;">측정된 플레이어 실력 점수: <b style="color:#fff;">${(diffData.score * 100).toFixed(0)}점</b></div>
      </div>

      <div style="margin: 10px 0 14px 0;">
        <span style="font-size: 11px; color: #a1a1aa; display: block; margin-bottom: 2px;">현재 플레이어 베팅 성향</span>
        <strong style="font-size: 15px; color: ${style.color};">${style.text}</strong>
      </div>
      
      <div style="background: #27272a; padding: 10px; border-radius: 6px; font-size: 11px; line-height: 1.5;">
        <div style="color: #f4f4f5; font-weight: bold; margin-bottom: 6px; border-bottom: 1px solid #52525b; padding-bottom: 2px;">누적 경기 데이터</div>
        <div style="display: flex; justify-content: space-between;">
          <span>총 전적 (완료된 게임):</span> <b>${displayedTotalHands}전 ${winCount}승 (${winRatePercent}%)</b>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 4px;">
          <span>레이즈 / 베팅 빈도:</span> <b style="color: #ef4444;">${table.user_raise_count || 0}회</b>
        </div>
        <div style="display: flex; justify-content: space-between;">
          <span>콜(Call) 유지 빈도:</span> <b style="color: #3b82f6;">${table.user_call_count || 0}회</b>
        </div>
        <div style="display: flex; justify-content: space-between;">
          <span>폴드(Fold) 포기 빈도:</span> <b style="color: #e4e4e7;">${table.user_fold_count || 0}회</b>
        </div>
      </div>
    </div>
  `;
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