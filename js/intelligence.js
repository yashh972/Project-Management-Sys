/* Intelligence layer UI: risk chips on issues, forecast modal on the task board. */
(function () {
	'use strict';

	var chip = document.getElementById('risk-chip');
	if (chip && chip.getAttribute('data-url')) {
		fetch(chip.getAttribute('data-url'), {
			credentials: 'same-origin',
			headers: { 'X-Requested-With': 'XMLHttpRequest' }
		})
			.then(function (response) { return response.json(); })
			.then(function (data) {
				if (data.error) {
					chip.classList.add('risk-unknown');
					chip.querySelector('.risk-label').textContent = 'Risk unavailable';
					chip.style.display = '';
					return;
				}

				var pct = Math.round((data.p_late || 0) * 100);
				var explanations = (data.explanation || []).slice(0, 3).map(function (item) {
					return item.feature + ' ' + (item.direction === 'increases' ? '↑' : '↓') + ' ' + Math.abs(item.impact).toFixed(2);
				});
				chip.classList.add('risk-' + data.risk);
				chip.querySelector('.risk-label').textContent = pct + '% late risk';
				chip.title = 'Predicted by ' + data.model + ' (' + data.model_version + ')'
					+ (explanations.length ? '\n' + explanations.join('\n') : '');
				chip.style.display = '';
			})
			.catch(function () {
				chip.classList.add('risk-unknown');
				chip.querySelector('.risk-label').textContent = 'Risk unavailable';
				chip.style.display = '';
			});
	}
})();
