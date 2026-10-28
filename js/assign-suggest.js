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
		var html = '';
		data.suggestions.forEach(function (s, i) {
			var tone = s.score >= 70 ? 'good' : (s.score >= 50 ? 'mid' : 'low');
			html += '<div class="assign-row' + (i === 0 ? ' best' : '') + '">' +
				'<span class="assign-score ' + tone + '" title="Fit score: likelihood of finishing on time plus spare capacity">' + s.score + '</span>' +
				'<div class="assign-main"><b>' + esc(s.name) + '</b>' + (i === 0 ? ' <span class="label label-primary">Best fit</span>' : '') +
				(s.limited_history ? ' <span class="label label-default">limited history</span>' : '') +
				'<div class="assign-meta">' + s.p_late + '% late risk &middot; about ' + s.expected_days + ' days &middot; ' + esc(s.reasons.join(' &middot; ').replace(/&middot;/g, '·')) + '</div></div>' +
				'<button type="button" class="btn btn-default btn-xs" data-owner="' + s.user_id + '">Assign</button></div>';
		});
		list.innerHTML = html;
		status.textContent = 'Model: ' + data.model.late_model + ', AUC ' + data.model.auc + ', trained on ' + data.model.tasks + ' tasks (' + data.model.trained_at + ' UTC).';
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

	list.addEventListener('click', function (e) {
		var b = e.target.closest('[data-owner]');
		if (!b) { return; }
		var sel = field('owner_id');
		if (sel) {
			sel.value = b.getAttribute('data-owner');
			sel.dispatchEvent(new Event('change', { bubbles: true }));
			status.textContent = 'Assignee set. ' + DEFAULT_HINT;
		}
	});
})();
