/* Sprint forecast modal: calls /intelligence/forecast/{sprint}. */
(function () {
	'use strict';

	var button = document.getElementById('forecast-btn');
	if (!button) { return; }

	var modal = document.getElementById('forecast-modal');
	var body = document.getElementById('forecast-body');

	function esc(value) {
		return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
			return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char];
		});
	}

	function open() {
		if (window.jQuery && modal) {
			window.jQuery(modal).modal('show');
		}
	}

	button.addEventListener('click', function () {
		open();
		if (!body) { return; }
		body.innerHTML = '<p class="text-muted">Running 5,000 delivery simulations…</p>';

		fetch(button.getAttribute('data-url') + '?simulations=5000', {
			credentials: 'same-origin',
			headers: { 'X-Requested-With': 'XMLHttpRequest' }
		})
			.then(function (response) { return response.json(); })
			.then(function (data) {
				if (data.error) {
					body.innerHTML = '<div class="alert alert-warning">' + esc(data.error) + '</div>';
					return;
				}

				var pct = Math.round((data.probability_on_time || 0) * 100);
				var tone = pct >= 70 ? 'success' : (pct >= 40 ? 'warning' : 'danger');
				var drivers = (data.drivers || []).map(function (driver) {
					return '<li><a href="' + esc(button.getAttribute('data-base') || '') + '/issues/' + driver.issue_id + '">'
						+ esc(driver.name) + '</a> — critical in '
						+ Math.round((driver.criticality || 0) * 100) + '% of simulations, median finish '
						+ esc(driver.median_finish) + '</li>';
				}).join('');

				body.innerHTML =
					'<div class="alert alert-' + tone + '"><b>' + pct + '%</b> chance of finishing this sprint on time '
					+ 'across ' + esc(data.open_tasks) + ' open tasks.</div>'
					+ '<p><b>P50:</b> ' + esc(data.p50_date) + ' &nbsp; <b>P85:</b> ' + esc(data.p85_date)
					+ ' &nbsp; <b>P95:</b> ' + esc(data.p95_date) + '</p>'
					+ (drivers ? '<p><b>Biggest drivers</b></p><ul class="forecast-drivers">' + drivers + '</ul>' : '')
					+ '<p class="text-muted">Assumptions: historical cycle times, ' + esc(data.assumptions.capacity_hours_per_day)
					+ 'h/day capacity, dependencies ' + esc(data.assumptions.dependency_cycle) + ', seed '
					+ esc(data.assumptions.seed) + '.</p>';
			})
			.catch(function () {
				body.innerHTML = '<div class="alert alert-warning">The forecast service is unavailable. Try again shortly.</div>';
			});
	});
})();
