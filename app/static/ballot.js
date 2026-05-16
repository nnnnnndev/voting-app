// Client-side helpers for ballot UIs. Works on mobile and desktop —
// click-to-rank, no drag required.

function setupApprovalBallot() {
  const form = document.getElementById('approval-form');
  if (!form) return;
  const cards = form.querySelectorAll('.fcard');
  cards.forEach(card => {
    card.addEventListener('click', (ev) => {
      if (ev.target.closest('.history-toggle')) return;
      if (card.classList.contains('ineligible')) return;
      card.classList.toggle('selected');
      updateApproval(form);
    });
  });
  updateApproval(form);
}

function updateApproval(form) {
  const ids = [];
  form.querySelectorAll('.fcard.selected').forEach(c => ids.push(c.dataset.id));
  form.querySelector('input[name=approved]').value = ids.join(',');
  const note = form.querySelector('.approval-note');
  if (note) note.textContent = ids.length + ' selected';
}

function setupRankedBallot() {
  const form = document.getElementById('ranked-form');
  if (!form) return;
  const maxRanks = parseInt(form.dataset.maxRanks, 10) || 5;
  const cards = form.querySelectorAll('.fcard');
  const ranking = [];

  function render() {
    cards.forEach(c => {
      const idx = ranking.indexOf(c.dataset.id);
      const badge = c.querySelector('.rank-num');
      if (idx >= 0) {
        c.classList.add('selected');
        c.classList.remove('unranked');
        badge.textContent = (idx + 1).toString();
      } else {
        c.classList.remove('selected');
        c.classList.add('unranked');
        badge.textContent = '';
      }
    });
    form.querySelector('input[name=ranking]').value = ranking.join(',');
    const note = form.querySelector('.ranked-note');
    if (note) note.textContent = ranking.length + ' of up to ' + maxRanks + ' ranked';
  }

  cards.forEach(card => {
    card.addEventListener('click', (ev) => {
      if (ev.target.closest('.history-toggle')) return;
      if (card.classList.contains('ineligible')) return;
      const id = card.dataset.id;
      const idx = ranking.indexOf(id);
      if (idx >= 0) {
        ranking.splice(idx, 1);
      } else if (ranking.length < maxRanks) {
        ranking.push(id);
      }
      render();
    });
  });
  render();
}

function setupHistoryToggles() {
  document.querySelectorAll('.history-toggle').forEach(btn => {
    btn.addEventListener('click', (ev) => {
      ev.stopPropagation();
      const card = btn.closest('.fcard');
      if (!card) return;
      const panel = card.querySelector('.history-panel');
      if (!panel) return;
      const open = !panel.hasAttribute('hidden');
      if (open) {
        panel.setAttribute('hidden', '');
        btn.classList.remove('open');
        btn.textContent = '+';
      } else {
        panel.removeAttribute('hidden');
        btn.classList.add('open');
        btn.textContent = '-';
      }
    });
  });
}

function setupYesNoBallot() {
  const form = document.getElementById('yes-no-form');
  if (!form) return;
  const choices = form.querySelectorAll('.choice');
  choices.forEach(c => {
    c.addEventListener('click', () => {
      choices.forEach(x => x.classList.remove('selected'));
      c.classList.add('selected');
      form.querySelector('input[name=choice]').value = c.dataset.value;
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  setupApprovalBallot();
  setupRankedBallot();
  setupYesNoBallot();
  setupHistoryToggles();
});
