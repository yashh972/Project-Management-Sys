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

				var box = document.getElementById('risk-explanation');
				if (box) {
					if (!data.explanation || !data.explanation.length) {
						box.style.display = 'none';
					} else {
						var maxImpact = Math.max.apply(null, data.explanation.map(function (item) {
							return Math.abs(item.impact);
						})) || 1;
						var rows = data.explanation.slice(0, 4).map(function (item) {
							var label = item.feature.replace(/_/g, ' ').replace(/\b[a-z]/g, function (char) {
								return char.toUpperCase();
							});
							var width = Math.max(4, Math.round(Math.abs(item.impact) / maxImpact * 100));
							var direction = item.direction === 'increases' ? 'increases' : 'decreases';
							var sign = item.impact >= 0 ? '+' : '−';
							return '<div class="risk-factor">'
								+ '<span class="risk-factor-name">' + label + '</span>'
								+ '<span class="risk-factor-bar"><i class="' + direction + '" style="width: ' + width + '%;"></i></span>'
								+ '<span class="risk-factor-impact ' + direction + '">' + sign + Math.abs(item.impact).toFixed(2) + '</span>'
								+ '</div>';
						}).join('');
						box.innerHTML = '<div class="risk-explanation-head"><b>Why this risk?</b><span>'
							+ data.model + ' · ' + data.model_version + '</span></div>' + rows;
						box.style.display = '';
					}
				}
			})
			.catch(function () {
				chip.classList.add('risk-unknown');
				chip.querySelector('.risk-label').textContent = 'Risk unavailable';
				chip.style.display = '';
			});
	}
})();
