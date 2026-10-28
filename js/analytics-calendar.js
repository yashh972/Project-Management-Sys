/* Interactive "tasks due" calendar on /analytics: week/month views, prev/next/today, click a day to list its tasks.
 * Data comes from window.AN.calendar (see Controller\Analytics). Falls back to the server-rendered week if absent. */
(function () {
	'use strict';
	var root = document.getElementById('an-cal');
	var data = window.AN && window.AN.calendar;
	if (!root || !data) { return; }

	var DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
	var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
	var MON = MONTHS.map(function (m) { return m.slice(0, 3); });

	function pad(n) { return (n < 10 ? '0' : '') + n; }
	function iso(d) { return d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate()); }
	function parse(s) { var p = s.split('-'); return new Date(Date.UTC(+p[0], +p[1] - 1, +p[2])); }
	function addDays(d, n) { return new Date(d.getTime() + n * 86400000); }
	function mondayOf(d) { return addDays(d, -((d.getUTCDay() + 6) % 7)); }
	function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
	function label(d) { return DOW[(d.getUTCDay() + 6) % 7] + ', ' + MON[d.getUTCMonth()] + ' ' + d.getUTCDate(); }

	var today = data.today;
	var byDay = {};
	data.tasks.forEach(function (t) { (byDay[t.due] = byDay[t.due] || []).push(t); });
	var dueDays = Object.keys(byDay).sort();

	var state = { view: 'week', anchor: parse(today), selected: today };

	function counts(day) {
		var list = byDay[day] || [], open = 0, late = 0;
		list.forEach(function (t) { if (!t.closed) { open++; if (day < today) { late++; } } });
		return { total: list.length, open: open, late: late };
	}

	function cell(d, muted) {
		var k = iso(d), c = counts(k);
		var cls = 'an-cal-day' + (k === today ? ' today' : '') + (k === state.selected ? ' sel' : '') + (muted ? ' muted' : '');
		var badge = c.total ? '<i class="' + (c.late ? 'late' : (c.open ? 'has' : 'done')) + '">' + c.total + '</i>' : '<i></i>';
		return '<button type="button" class="' + cls + '" data-day="' + k + '" aria-label="' + esc(label(d)) + ', ' + c.total + ' due">' +
			'<small>' + DOW[(d.getUTCDay() + 6) % 7] + '</small><b>' + d.getUTCDate() + '</b>' + badge + '</button>';
	}

	function grid() {
		var out = '', d, i;
		if (state.view === 'week') {
			d = mondayOf(state.anchor);
			out = '<div class="an-cal-grid week">';
			for (i = 0; i < 7; i++) { out += cell(addDays(d, i), false); }
			return out + '</div>';
		}
		var first = new Date(Date.UTC(state.anchor.getUTCFullYear(), state.anchor.getUTCMonth(), 1));
		var start = mondayOf(first), m = first.getUTCMonth();
		out = '<div class="an-cal-head">' + DOW.map(function (n) { return '<span>' + n + '</span>'; }).join('') + '</div><div class="an-cal-grid month">';
		for (i = 0; i < 42; i++) {
			d = addDays(start, i);
			if (i >= 35 && d.getUTCMonth() !== m) { break; }
			out += cell(d, d.getUTCMonth() !== m);
		}
		return out + '</div>';
	}

	function title() {
		if (state.view === 'month') { return MONTHS[state.anchor.getUTCMonth()] + ' ' + state.anchor.getUTCFullYear(); }
		var a = mondayOf(state.anchor), b = addDays(a, 6);
		return a.getUTCMonth() === b.getUTCMonth() ? MONTHS[a.getUTCMonth()] + ' ' + a.getUTCFullYear() : MON[a.getUTCMonth()] + ' - ' + MON[b.getUTCMonth()] + ' ' + b.getUTCFullYear();
	}

	function list() {
		var sel = state.selected, tasks = (byDay[sel] || []).slice();
		tasks.sort(function (a, b) { return (a.closed - b.closed) || a.name.localeCompare(b.name); });
		var d = parse(sel), html = '<div class="an-cal-sub">' + (sel === today ? 'Today' : esc(label(d))) + ' &middot; ' + tasks.length + ' task' + (tasks.length === 1 ? '' : 's') + ' due</div>';
		if (!tasks.length) {
			var next = dueDays.filter(function (k) { return k > sel && counts(k).open; })[0];
			return html + '<p class="an-muted an-cal-empty">Nothing due.' + (next ? ' <a href="#" data-day="' + next + '">Next due: ' + esc(label(parse(next))) + '</a>' : '') + '</p>';
		}
		html += '<ul class="an-list">';
		tasks.forEach(function (t) {
			var over = !t.closed && t.due < today;
			html += '<li class="' + (over ? 'over' : '') + (t.closed ? ' closed' : '') + '"><a href="' + esc(data.base) + '/issues/' + t.id + '"><b>' + esc(t.name) + '</b>' +
				'<small>' + (t.closed ? 'Completed' : (over ? 'Overdue' : 'Open')) + (t.project ? ' &middot; ' + esc(t.project) : '') +
				(!t.closed && t.risk !== null && t.risk >= 40 ? ' &middot; ' + t.risk + '% late risk' : '') + '</small></a>' +
				(t.owner ? '<span class="an-av sm" style="--c: ' + esc(t.owner.color) + '" title="' + esc(t.owner.name) + '">' + esc(t.owner.initials) + '</span>' : '') + '</li>';
		});
		return html + '</ul>';
	}

	function render() {
		root.innerHTML =
			'<div class="an-card-head"><h2>' + esc(title()) + '</h2>' +
			'<div class="an-cal-ctl"><button type="button" data-act="prev" aria-label="Previous">&lsaquo;</button>' +
			'<button type="button" data-act="today" class="txt">Today</button>' +
			'<button type="button" data-act="next" aria-label="Next">&rsaquo;</button></div></div>' +
			'<div class="an-cal-views"><button type="button" data-view="week" class="' + (state.view === 'week' ? 'on' : '') + '">Week</button>' +
			'<button type="button" data-view="month" class="' + (state.view === 'month' ? 'on' : '') + '">Month</button></div>' +
			grid() + list();
	}

	function select(k) {
		state.selected = k;
		state.anchor = parse(k);
		render();
	}

	root.addEventListener('click', function (e) {
		var el = e.target.closest('[data-day],[data-act],[data-view]');
		if (!el || !root.contains(el)) { return; }
		if (el.hasAttribute('data-day')) { e.preventDefault(); select(el.getAttribute('data-day')); return; }
		if (el.hasAttribute('data-view')) { state.view = el.getAttribute('data-view'); render(); return; }
		var step = state.view === 'week' ? 7 : 0, act = el.getAttribute('data-act');
		if (act === 'today') {
			state.selected = today;
			state.anchor = parse(today);
		} else {
			var dir = act === 'next' ? 1 : -1;
			if (step) {
				state.anchor = addDays(state.anchor, dir * step);
			} else {
				state.anchor = new Date(Date.UTC(state.anchor.getUTCFullYear(), state.anchor.getUTCMonth() + dir, 1));
			}
			// keep the selected day inside the visible range so the list always matches the grid
			state.selected = iso(step ? addDays(parse(state.selected), dir * step) : state.anchor);
		}
		render();
	});

	render();
})();
