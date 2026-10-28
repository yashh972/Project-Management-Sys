/* Prescriptive sprint assignment: preview the optimizer's recommendations. */
(function () {
	'use strict';

	var button = document.getElementById('optimize-btn');
	if (!button) { return; }

	var modal = document.getElementById('optimize-modal');
	var body = document.getElementById('optimize-body');
	var applyButton = document.getElementById('optimize-apply');
	var lastAssignments = [];

	function esc(value) {
		return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
			return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char];
		});
	}

	button.addEventListener('click', function () {
		if (window.jQuery && modal) { window.jQuery(modal).modal('show'); }
		if (!body) { return; }
		lastAssignments = [];
		if (applyButton) { applyButton.style.display = 'none'; }
		body.innerHTML = '<p class="text-muted">Solving the sprint assignment problem…</p>';

		var csrf = document.querySelector('meta[name="csrf-token"]');
		var params = new URLSearchParams();
		params.set('csrf-token', csrf ? csrf.getAttribute('content') : '');
		params.set('sprint_id', button.getAttribute('data-sprint'));
		params.set('capacity_hours', '40');
		params.set('max_wip', '3');
		params.set('fairness', '1');

		fetch(button.getAttribute('data-url'), {
			method: 'POST',
			credentials: 'same-origin',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded',
				'X-Requested-With': 'XMLHttpRequest'
			},
			body: params.toString()
		})
			.then(function (response) { return response.json(); })
			.then(function (data) {
				if (data.error) {
					body.innerHTML = '<div class="alert alert-warning">' + esc(data.error) + '</div>';
					return;
				}

				var summary = data.summary || {};
				var loads = (summary.loads || []).map(function (load) {
					return '<span class="label label-default">' + esc(load.user_name) + ': ' + load.hours
						+ 'h / ' + load.capacity + 'h</span>';
				}).join(' ');
				var rows = (data.assignments || []).map(function (assignment) {
					return '<tr>' +
						'<td><a href="' + esc(button.getAttribute('data-base')) + '/issues/' + assignment.issue_id + '">'
						+ esc(assignment.issue_name) + '</a></td>' +
						'<td>' + (assignment.current_owner_id ? 'current owner' : '<em>unassigned</em>') + '</td>' +
						'<td><b>' + esc(assignment.user_name) + '</b></td>' +
						'<td>' + assignment.score + '</td>' +
						'<td>' + assignment.hours + 'h</td>' +
						'<td>' + (assignment.changed ? '<span class="label label-warning">change</span>' : '<span class="label label-default">keep</span>') + '</td>' +
						'</tr>';
				}).join('');

				lastAssignments = data.assignments || [];
				body.innerHTML =
					'<div class="alert alert-info">Solver: <b>' + esc(data.solver) + '</b> · expected fit '
					+ summary.expected_fit + '/100 · baseline ' + summary.baseline_fit
					+ ' · lift <b>' + summary.lift + '</b> · ' + summary.changed + ' owner change(s)'
					+ ' · fairness <b>' + (summary.fairness_applied ? 'on (cap ' + summary.fairness_cap + 'h)' : 'off') + '</b>.</div>'
					+ (rows ? '<table class="table table-condensed table-striped"><thead><tr><th>Task</th><th>Now</th><th>Suggested</th><th>Fit</th><th>Hours</th><th></th></tr></thead><tbody>'
						+ rows + '</tbody></table>' : '<p>No assignments found.</p>')
					+ (loads ? '<p>' + loads + '</p>' : '')
					+ '<p class="text-muted">Review the recommendations before applying them. Every change is recorded in the issue history.</p>';

				if (applyButton) {
					var canApply = button.getAttribute('data-can-apply') === '1';
					var hasChanges = Number(summary.changed || 0) > 0;
					applyButton.style.display = canApply && hasChanges ? '' : 'none';
				}
			})
			.catch(function () {
				body.innerHTML = '<div class="alert alert-warning">The optimizer is unavailable. Try again shortly.</div>';
			});
	});

	if (applyButton) {
		applyButton.addEventListener('click', function () {
			if (!lastAssignments.length) { return; }

			applyButton.disabled = true;
			var csrf = document.querySelector('meta[name="csrf-token"]');
			var params = new URLSearchParams();
			params.set('csrf-token', csrf ? csrf.getAttribute('content') : '');
			params.set('sprint_id', button.getAttribute('data-sprint'));
			params.set('assignments', JSON.stringify(lastAssignments.map(function (assignment) {
				return {
					issue_id: assignment.issue_id,
					user_id: assignment.user_id,
					score: assignment.score,
					hours: assignment.hours
				};
			})));

			fetch(button.getAttribute('data-base') + '/intelligence/optimize/apply', {
				method: 'POST',
				credentials: 'same-origin',
				headers: {
					'Content-Type': 'application/x-www-form-urlencoded',
					'X-Requested-With': 'XMLHttpRequest'
				},
				body: params.toString()
			})
				.then(function (response) { return response.json(); })
				.then(function (data) {
					if (data.error) {
						body.insertAdjacentHTML('afterbegin', '<div class="alert alert-warning">' + esc(data.error) + '</div>');
						applyButton.disabled = false;
						return;
					}
					window.location.reload();
				})
				.catch(function () {
					body.insertAdjacentHTML('afterbegin', '<div class="alert alert-warning">Could not apply the assignments.</div>');
					applyButton.disabled = false;
				});
		});
	}
})();
