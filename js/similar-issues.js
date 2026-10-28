/* Similar-issue suggestions for duplicate detection. */
(function () {
	'use strict';

	function esc(value) {
		return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
			return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char];
		});
	}

	function render(container, results, draftMode) {
		if (!results || !results.length) {
			container.innerHTML = '<li class="text-muted">No close matches.</li>';
			return;
		}

		var top = results[0].score || 0;
		var html = '';
		if (draftMode && top >= 0.4) {
			html += '<li class="similar-warning"><span class="fa fa-exclamation-triangle"></span> Possible duplicate — review before creating.</li>';
		}
		html += results.slice(0, 4).map(function (item) {
			return '<li><a href="' + esc(BASE) + '/issues/' + item.issue_id + '">' + esc(item.name) + '</a>'
				+ '<span class="similar-score">' + Math.round((item.score || 0) * 100) + '%</span></li>';
		}).join('');
		container.innerHTML = html;
	}

	var existing = document.getElementById('similar-issues');
	if (existing && existing.getAttribute('data-url')) {
		var list = existing.querySelector('ul');
		fetch(existing.getAttribute('data-url'), {
			credentials: 'same-origin',
			headers: { 'X-Requested-With': 'XMLHttpRequest' }
		})
			.then(function (response) { return response.json(); })
			.then(function (data) { render(list, data.results, false); })
			.catch(function () { list.innerHTML = '<li class="text-muted">Similarity search unavailable.</li>'; });
	}

	var draft = document.getElementById('similar-draft');
	if (!draft) { return; }

	var nameField = document.querySelector('#edit-form [name="name"]');
	var descriptionField = document.querySelector('#edit-form [name="description"]');
	var draftResults = document.getElementById('similar-draft-results');
	if (!nameField || !descriptionField || !draftResults) { return; }

	var timer = null;
	function check() {
		var name = (nameField.value || '').trim();
		var description = (descriptionField.value || '').trim();
		if (name.length < 4 && description.length < 12) {
			draftResults.innerHTML = '';
			return;
		}

		var params = new URLSearchParams();
		params.set('text', name + ' ' + description);
		fetch(draft.getAttribute('data-url'), {
			method: 'POST',
			credentials: 'same-origin',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded',
				'X-Requested-With': 'XMLHttpRequest'
			},
			body: params.toString()
		})
			.then(function (response) { return response.json(); })
			.then(function (data) { render(draftResults, data.results, true); })
			.catch(function () { draftResults.innerHTML = ''; });
	}

	function schedule() {
		window.clearTimeout(timer);
		timer = window.setTimeout(check, 650);
	}

	nameField.addEventListener('input', schedule);
	descriptionField.addEventListener('input', schedule);
})();
