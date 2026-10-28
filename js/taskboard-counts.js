/* Keeps the per-column task counts in the taskboard header correct after cards are dragged or added. */
(function () {
	'use strict';
	var table = document.getElementById('task-table');
	if (!table) { return; }

	function update() {
		var counts = {};
		table.querySelectorAll('td.droppable[data-status]').forEach(function (td) {
			var s = td.getAttribute('data-status');
			counts[s] = (counts[s] || 0) + td.querySelectorAll('.card.task:not(.placeholder)').length;
		});
		document.querySelectorAll('.taskboard-head th.tb-status').forEach(function (th) {
			var m = /tb-status-(\d+)/.exec(th.className), el = th.querySelector('.tb-count');
			if (m && el) { el.textContent = counts[m[1]] || 0; }
		});
	}

	new MutationObserver(update).observe(table, { childList: true, subtree: true });
	update();
})();
