/* Grounded project assistant on the command center. */
(function () {
	'use strict';

	var root = document.getElementById('assistant');
	if (!root) { return; }

	var form = document.getElementById('assistant-form');
	var input = document.getElementById('assistant-input');
	var answer = document.getElementById('assistant-answer');
	var sprint = root.getAttribute('data-sprint') || '';

	function esc(value) {
		return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
			return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char];
		});
	}

	function render(data) {
		if (data.error) {
			answer.innerHTML = '<div class="alert alert-warning">' + esc(data.error) + '</div>';
			return;
		}

		var citations = (data.citations || []).map(function (citation) {
			return '<a href="' + esc((typeof BASE !== 'undefined' ? BASE : '') + citation.url) + '">' + esc(citation.label) + '</a>';
		}).join(' · ');

		answer.innerHTML = '<p class="assistant-text">' + esc(data.answer) + '</p>'
			+ (citations ? '<div class="assistant-citations"><span>Sources:</span> ' + citations + '</div>' : '');
	}

	function ask(question) {
		if (!question.trim()) { return; }
		answer.innerHTML = '<p class="text-muted">Reading the project data…</p>';
		var params = new URLSearchParams();
		params.set('question', question);
		if (sprint) { params.set('sprint_id', sprint); }

		fetch(root.getAttribute('data-url'), {
			method: 'POST',
			credentials: 'same-origin',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded',
				'X-Requested-With': 'XMLHttpRequest'
			},
			body: params.toString()
		})
			.then(function (response) { return response.json(); })
			.then(render)
			.catch(function () {
				answer.innerHTML = '<div class="alert alert-warning">The assistant is unavailable. Try again shortly.</div>';
			});
	}

	if (form) {
		form.addEventListener('submit', function (event) {
			event.preventDefault();
			ask(input.value);
		});
	}

	root.querySelectorAll('[data-q]').forEach(function (button) {
		button.addEventListener('click', function () {
			input.value = button.getAttribute('data-q');
			ask(input.value);
		});
	});
})();
