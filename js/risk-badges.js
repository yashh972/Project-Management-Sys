/* Add calibrated late-risk badges to task-board cards and issue-list rows. */
(function () {
	'use strict';

	var elements = Array.prototype.slice.call(
		document.querySelectorAll('.card.task[data-id], tr[data-id]')
	);
	if (!elements.length || typeof BASE === 'undefined') { return; }

	var ids = elements.map(function (element) { return element.getAttribute('data-id'); }).filter(Boolean);
	if (!ids.length) { return; }

	fetch(BASE + '/intelligence/risk-batch?ids=' + encodeURIComponent(ids.join(',')), {
		credentials: 'same-origin',
		headers: { 'X-Requested-With': 'XMLHttpRequest' }
	})
		.then(function (response) { return response.json(); })
		.then(function (data) {
			(data.results || []).forEach(function (result) {
				if (result.error || result.p_late == null) { return; }
				var element = document.getElementById('task_' + result.issue_id)
					|| document.querySelector('tr[data-id="' + result.issue_id + '"]');
				if (!element || element.querySelector('.risk-badge')) { return; }

				var percent = Math.round(result.p_late * 100);
				var badge = document.createElement('span');
				badge.className = 'risk-badge risk-' + result.risk;
				badge.textContent = percent + '%';
				badge.title = 'Predicted late risk: ' + percent + '% (' + result.risk + ')';

				if (element.classList.contains('card')) {
					var top = element.querySelector('.top');
					if (top) {
						top.insertBefore(badge, top.firstChild);
					} else {
						element.appendChild(badge);
					}
				} else {
					var title = element.querySelector('.issue-title');
					if (title) {
						title.appendChild(badge);
					}
				}
			});
		})
		.catch(function () { /* risk badges are best-effort */ });
})();
