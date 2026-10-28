/* Smart assignment widget on the issue form: asks /assign/suggest for a ranked list and lets you pick an owner. */
(function () {
	'use strict';
	var box = document.getElementById('assign-suggest');
	if (!box) { return; }
	var btn = document.getElementById('assign-suggest-btn');
	var status = document.getElementById('assign-suggest-status');
	var list = document.getElementById('assign-suggest-list');
	var form = document.getElementById('edit-form') || box.closest('form');
	var DEFAULT_HINT = status.textContent;
	var lastRecommendation = null;

	function field(name) { return form ? form.querySelector('[name="' + name + '"]') : null; }
	function val(name) { var f = field(name); return f ? f.value : ''; }
	function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

	function tags() {
		var seen = {}, out = [], m, re = /(^|\s)#([A-Za-z0-9_-]+)/g, text = val('description');
		while ((m = re.exec(text))) { if (!seen[m[2].toLowerCase()]) { seen[m[2].toLowerCase()] = 1; out.push(m[2].toLowerCase()); } }
		return out.join(',');
	}

	function query() {
		var hours = parseFloat(val('hours_total')) || parseFloat(val('hours_remaining')) || '';
		var p = { type_id: val('type_id') || 1, priority: val('priority') || 0, due: val('due_date'), tags: tags(), hours: hours };
		return Object.keys(p).filter(function (k) { return p[k] !== '' && p[k] !== null; }).map(function (k) { return k + '=' + encodeURIComponent(p[k]); }).join('&');
	}

	function render(data) {
		var rec = data.recommendations && data.recommendations[0];
		if (!rec || !rec.candidates || !rec.candidates.length) {
			status.textContent = 'No candidates are available for this task.';
			return;
		}

		var html = '';
		lastRecommendation = rec;
		rec.candidates.forEach(function (s, i) {
			var tone = s.score >= 70 ? 'good' : (s.score >= 50 ? 'mid' : 'low');
			var onTime = Math.round((s.p_on_time || 0) * 100);
			html += '<div class="assign-row' + (i === 0 ? ' best' : '') + '">' +
				'<span class="assign-score ' + tone + '" title="Fit score: likelihood of finishing on time plus spare capacity">' + s.score + '</span>' +
				'<div class="assign-main"><b>' + esc(s.name) + '</b>' + (i === 0 ? ' <span class="label label-primary">Best fit</span>' : '') +
				(s.limited_history ? ' <span class="label label-default">limited history</span>' : '') +
				'<div class="assign-meta">' + onTime + '% on-time &middot; ' + s.open_hours + 'h open &middot; ' + esc((s.reasons || []).join(' · ')) + '</div></div>' +
				'<button type="button" class="btn btn-default btn-xs" data-owner="' + s.user_id + '">Assign</button></div>';
		});
		list.innerHTML = html;
		status.textContent = 'Ranked by the assignment service using on-time history, current load and tag overlap.';
	}

	btn.addEventListener('click', function () {
		btn.disabled = true;
		list.innerHTML = '';
		status.textContent = 'Scoring the team...';
		fetch(box.getAttribute('data-url') + '?' + query(), { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
			.then(function (r) { return r.json(); })
			.then(function (d) {
				if (d.error) { status.textContent = d.error; return; }
				render(d);
			})
			.catch(function () { status.textContent = 'Could not reach the assignment model.'; })
			.then(function () { btn.disabled = false; });
	});

	function logAcceptance(ownerId) {
		var rec = lastRecommendation;
		if (!rec) { return; }
		var csrf = document.querySelector('meta[name="csrf-token"]');
		var base = box.getAttribute('data-url').replace(/\/assign\/suggest$/, '');
		var chosen = null;
		(rec.candidates || []).forEach(function (candidate) {
			if (String(candidate.user_id) === String(ownerId)) { chosen = candidate; }
		});

		var params = new URLSearchParams();
		params.set('csrf-token', csrf ? csrf.getAttribute('content') : '');
		params.set('kind', 'assignment');
		params.set('action', 'accepted');
		params.set('issue_id', rec.issue_id || '');
		params.set('payload', JSON.stringify({
			issue_id: rec.issue_id || null,
			selected_user_id: Number(ownerId),
			selected: chosen,
			candidates: rec.candidates
		}));

		fetch(base + '/intelligence/suggestions/log', {
			method: 'POST',
			credentials: 'same-origin',
			headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
			body: params.toString()
		}).catch(function () { /* feedback is best-effort */ });
	}

	list.addEventListener('click', function (e) {
		var b = e.target.closest('[data-owner]');
		if (!b) { return; }
		var sel = field('owner_id');
		if (sel) {
			sel.value = b.getAttribute('data-owner');
			sel.dispatchEvent(new Event('change', { bubbles: true }));
			status.textContent = 'Assignee set. ' + DEFAULT_HINT;
			logAcceptance(b.getAttribute('data-owner'));
		}
	});
})();
