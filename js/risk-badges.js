/* Add calibrated late-risk badges to task-board cards. */
(function () {
	'use strict';

	var cards = Array.prototype.slice.call(document.querySelectorAll('.card.task[data-id]'));
	if (!cards.length || typeof BASE === 'undefined') { return; }

	var ids = cards.map(function (card) { return card.getAttribute('data-id'); }).filter(Boolean);
	if (!ids.length) { return; }

	fetch(BASE + '/intelligence/risk-batch?ids=' + encodeURIComponent(ids.join(',')), {
		credentials: 'same-origin',
		headers: { 'X-Requested-With': 'XMLHttpRequest' }
	})
		.then(function (response) { return response.json(); })
		.then(function (data) {
			(data.results || []).forEach(function (result) {
				if (result.error || result.p_late == null) { return; }
				var card = document.getElementById('task_' + result.issue_id);
				if (!card || card.querySelector('.risk-badge')) { return; }

				var percent = Math.round(result.p_late * 100);
				var badge = document.createElement('span');
				badge.className = 'risk-badge risk-' + result.risk;
				badge.textContent = percent + '%';
				badge.title = 'Predicted late risk: ' + percent + '% (' + result.risk + ')';
				var top = card.querySelector('.top');
				if (top) {
					top.insertBefore(badge, top.firstChild);
				} else {
					card.appendChild(badge);
				}
			});
		})
		.catch(function () { /* risk badges are best-effort */ });
})();
