/* Notification center: unread badge polling and per-item read marking. */
(function () {
	'use strict';

	var badge = document.getElementById('notification-badge');
	if (!badge && !document.body.classList.contains('notifications-page')) { return; }

	function setCount(count) {
		if (!badge) { return; }
		badge.textContent = count > 0 ? String(count) : '';
		badge.style.display = count > 0 ? '' : 'none';
	}

	function refreshCount() {
		if (typeof BASE === 'undefined') { return; }
		fetch(BASE + '/notifications/count', {
			credentials: 'same-origin',
			headers: { 'X-Requested-With': 'XMLHttpRequest' }
		})
			.then(function (response) { return response.json(); })
			.then(function (data) { setCount(Number(data.count || 0)); })
			.catch(function () { /* best-effort */ });
	}

	if (badge) {
		refreshCount();
		setInterval(refreshCount, 60000);
	}

	var csrf = document.querySelector('meta[name="csrf-token"]');

	function markRead(payload) {
		if (typeof BASE === 'undefined' || !csrf) { return Promise.resolve(); }
		var params = new URLSearchParams();
		params.set('csrf-token', csrf.getAttribute('content'));
		Object.keys(payload).forEach(function (key) { params.set(key, payload[key]); });
		params.set('ajax', '1');
		return fetch(BASE + '/notifications/read', {
			method: 'POST',
			credentials: 'same-origin',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded',
				'X-Requested-With': 'XMLHttpRequest'
			},
			body: params.toString()
		}).then(function (response) { return response.json(); });
	}

	document.querySelectorAll('[data-notification-id]').forEach(function (link) {
		link.addEventListener('click', function () {
			markRead({ id: link.getAttribute('data-notification-id') });
		});
	});

	var markAll = document.getElementById('notifications-mark-all');
	if (markAll) {
		markAll.addEventListener('click', function (event) {
			event.preventDefault();
			markRead({ all: '1' }).then(function () { window.location.reload(); });
		});
	}
})();
