/* Sprint forecast modal with what-if scenarios. */
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

	function load(options) {
		if (!body) { return; }
		options = options || {};
		var extraDays = Number(options.extra_days || 0);
		var capacityMultiplier = Number(options.capacity_multiplier || 1);

		var params = new URLSearchParams();
		params.set('simulations', '5000');
		if (extraDays !== 0) { params.set('extra_days', String(extraDays)); }
		if (capacityMultiplier !== 1) { params.set('capacity_multiplier', String(capacityMultiplier)); }

		body.innerHTML = '<p class="text-muted">Running 5,000 delivery simulations…</p>';

		fetch(button.getAttribute('data-url') + '?' + params.toString(), {
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
				var scenario = extraDays !== 0 || capacityMultiplier !== 1
					? '<span class="label label-info">Scenario: '
						+ (extraDays !== 0 ? (extraDays > 0 ? '+' : '') + extraDays + ' days ' : '')
						+ (capacityMultiplier !== 1 ? Math.round(capacityMultiplier * 100) + '% capacity ' : '')
						+ '</span>'
					: '';

				body.innerHTML =
					'<div class="alert alert-' + tone + '"><b>' + pct + '%</b> chance of finishing this sprint on time '
					+ 'across ' + esc(data.open_tasks) + ' open tasks. ' + scenario + '</div>'
					+ '<p><b>P50:</b> ' + esc(data.p50_date) + ' &nbsp; <b>P85:</b> ' + esc(data.p85_date)
					+ ' &nbsp; <b>P95:</b> ' + esc(data.p95_date) + '</p>'
					+ (drivers ? '<p><b>Biggest drivers</b></p><ul class="forecast-drivers">' + drivers + '</ul>' : '')
					+ '<p class="text-muted">Assumptions: historical cycle times, '
					+ esc(data.assumptions.capacity_hours_per_day) + 'h/day capacity, dependencies '
					+ esc(data.assumptions.dependency_cycle) + ', seed ' + esc(data.assumptions.seed) + '.</p>'
					+ '<div class="forecast-whatif"><b>What if:</b> '
					+ '<button type="button" class="btn btn-default btn-xs" data-shift="3">+3 days</button>'
					+ '<button type="button" class="btn btn-default btn-xs" data-shift="7">+7 days</button>'
					+ '<button type="button" class="btn btn-default btn-xs" data-cap="0.8">−20% capacity</button>'
					+ '<button type="button" class="btn btn-default btn-xs" data-cap="1.2">+20% capacity</button>'
					+ '<button type="button" class="btn btn-link btn-xs" data-reset="1">Reset</button></div>';

				body.querySelectorAll('[data-shift]').forEach(function (element) {
					element.addEventListener('click', function () {
						load({ extra_days: Number(element.getAttribute('data-shift')) });
					});
				});
				body.querySelectorAll('[data-cap]').forEach(function (element) {
					element.addEventListener('click', function () {
						load({ capacity_multiplier: Number(element.getAttribute('data-cap')) });
					});
				});
				var reset = body.querySelector('[data-reset]');
				if (reset) {
					reset.addEventListener('click', function () { load({}); });
				}
			})
			.catch(function () {
				body.innerHTML = '<div class="alert alert-warning">The forecast service is unavailable. Try again shortly.</div>';
			});
	}

	button.addEventListener('click', function () {
		if (window.jQuery && modal) { window.jQuery(modal).modal('show'); }
		load({});
	});
})();
