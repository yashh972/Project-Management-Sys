/* Admin analytics dashboard: section tabs, performance chart and head-to-head employee comparison.
 * Data comes from window.AN (see Controller\Analytics). */
(function () {
	'use strict';
	var D = window.AN || {};
	if (typeof Chart === 'undefined') { return; }

	var css = getComputedStyle(document.documentElement);
	var cv = function (n, f) { return (css.getPropertyValue(n) || f).trim() || f; };
	var TEXT2 = cv('--text-2', '#5a5d72'), TEXT3 = cv('--text-3', '#8a8da2'), BORDER = cv('--border', '#ebecf2');
	Chart.defaults.font.family = cv('--font-sans', 'Inter, system-ui, sans-serif');
	Chart.defaults.color = TEXT3;

	var onShow = {};   // tab name -> callback run every time that tab becomes visible

	/* ------------------------------------------------------------ tabs */
	var tabs = Array.prototype.slice.call(document.querySelectorAll('.an-tabs [data-tab]'));
	var panes = {};
	tabs.forEach(function (t) { panes[t.getAttribute('data-tab')] = document.getElementById('pane-' + t.getAttribute('data-tab')); });

	function keepHash(name) {
		// keep the chosen tab when switching period or recomputing insights
		document.querySelectorAll('#an-range a').forEach(function (a) { a.href = a.href.split('#')[0] + '#' + name; });
		var f = document.getElementById('an-refresh');
		if (f) { f.action = f.action.split('#')[0] + '#' + name; }
	}

	function show(name, updateHash) {
		if (!panes[name]) { name = 'overview'; }
		tabs.forEach(function (t) {
			var on = t.getAttribute('data-tab') === name;
			t.classList.toggle('active', on);
			t.setAttribute('aria-selected', on ? 'true' : 'false');
			panes[t.getAttribute('data-tab')].hidden = !on;
		});
		keepHash(name);
		if (updateHash && history.replaceState) { history.replaceState(null, '', '#' + name); }
		if (onShow[name]) { onShow[name](); }
	}

	tabs.forEach(function (t) {
		t.addEventListener('click', function () { show(t.getAttribute('data-tab'), true); });
		t.addEventListener('keydown', function (e) {
			var i = tabs.indexOf(t), n = null;
			if (e.key === 'ArrowRight') { n = tabs[(i + 1) % tabs.length]; }
			if (e.key === 'ArrowLeft') { n = tabs[(i - 1 + tabs.length) % tabs.length]; }
			if (n) { e.preventDefault(); n.focus(); show(n.getAttribute('data-tab'), true); }
		});
	});

	/* ------------------------------------------------------------ area chart (Overview) */
	var chart = null;
	var canvas = document.getElementById('an-chart');
	if (canvas && D.chart) {
		var ctx = canvas.getContext('2d');
		var fill = function (hex) {
			var g = ctx.createLinearGradient(0, 0, 0, 330);
			g.addColorStop(0, hex + '80');
			g.addColorStop(1, hex + '06');
			return g;
		};
		var mk = function (label, data, hex) {
			return {
				label: label, data: data, borderColor: hex, backgroundColor: fill(hex), fill: true, tension: 0.42,
				borderWidth: 2.5, pointRadius: 0, pointHoverRadius: 6, pointHoverBackgroundColor: '#fff',
				pointHoverBorderColor: hex, pointHoverBorderWidth: 3
			};
		};
		chart = new Chart(ctx, {
			type: 'line',
			data: { labels: D.chart.labels, datasets: [mk('Completed', D.chart.completed, '#5b8dff'), mk('Created', D.chart.created, '#a58bff')] },
			options: {
				responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
				plugins: {
					legend: { display: false },
					tooltip: {
						backgroundColor: '#ffffff', titleColor: '#15161f', bodyColor: '#5a5d72', borderColor: BORDER, borderWidth: 1,
						padding: 12, cornerRadius: 12, boxPadding: 6, usePointStyle: true,
						titleFont: { weight: '600', size: 12 }, bodyFont: { size: 12.5 }
					}
				},
				scales: {
					x: { grid: { display: false }, border: { display: false }, ticks: { maxTicksLimit: 8, maxRotation: 0 } },
					y: { beginAtZero: true, border: { display: false }, grid: { color: BORDER }, ticks: { precision: 0, maxTicksLimit: 5 } }
				}
			}
		});
		var legend = document.getElementById('an-legend');
		if (legend) {
			legend.addEventListener('click', function (e) {
				var b = e.target.closest('button[data-ds]');
				if (!b) { return; }
				var i = +b.getAttribute('data-ds');
				var visible = !chart.isDatasetVisible(i);
				chart.setDatasetVisibility(i, visible);
				b.classList.toggle('on', visible);
				chart.update();
			});
		}
		onShow.overview = function () { chart.resize(); };
	}

	/* ------------------------------------------------------------ head-to-head compare */
	var emps = (D.employees || []).filter(function (e) { return e.score !== null; });
	var selA = document.getElementById('cmp-a');
	var selB = document.getElementById('cmp-b');
	var radarEl = document.getElementById('cmp-radar');
	if (selA && selB && radarEl && emps.length > 1) {
		var byId = {};
		emps.forEach(function (e) { byId[e.id] = e; });
		var COL_A = '#5b6cf6', COL_B = '#e0559b';
		var AXES = [['reliability', 'Reliability'], ['speed', 'Speed'], ['quality', 'Quality'], ['estimation', 'Estimation'], ['volume', 'Volume']];
		var esc = function (s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; };

		var radar = new Chart(radarEl.getContext('2d'), {
			type: 'radar',
			data: { labels: AXES.map(function (a) { return a[1]; }), datasets: [] },
			options: {
				responsive: true, maintainAspectRatio: false,
				scales: { r: { min: 0, max: 100, ticks: { display: false, stepSize: 25 }, grid: { color: BORDER }, angleLines: { color: BORDER }, pointLabels: { color: TEXT2, font: { size: 12, weight: '500' } } } },
				plugins: { legend: { display: false } }
			}
		});

		// metric rows: label, value getter, display, "high" or "low" is better
		var METRICS = [
			['Overall score', function (e) { return e.score; }, function (e) { return e.score.toFixed(1); }, 'high'],
			['Tasks completed', function (e) { return e.tasks; }, function (e) { return e.tasks; }, 'high'],
			['On-time rate', function (e) { return e.on_time; }, function (e) { return e.on_time + '%'; }, 'high'],
			['Speed vs expected', function (e) { return e.speed; }, function (e) { return e.speed + '×'; }, 'high'],
			['Avg days late', function (e) { return e.late_days; }, function (e) { return e.late_days; }, 'low'],
			['Rework (reopened)', function (e) { return e.reopen; }, function (e) { return e.reopen + '%'; }, 'low'],
			['Estimate accuracy', function (e) { return e.estimate; }, function (e) { return e.estimate + '%'; }, 'high'],
			['Tasks per week', function (e) { return e.throughput; }, function (e) { return e.throughput; }, 'high'],
			['Hours delivered (12w)', function (e) { return e.hours; }, function (e) { return e.hours; }, 'high'],
			['30-day trend', function (e) { return e.trend; }, function (e) { return (e.trend > 0 ? '+' : '') + e.trend + ' pts'; }, 'high']
		];

		var profile = function (e, side) {
			return '<span class="an-av lg" style="--c:' + e.color + '">' + esc(e.initials) + '</span>' +
				'<h3>' + esc(e.name) + '</h3>' +
				'<span class="an-cluster an-cl-' + e.cluster_key + '">' + esc(e.cluster) + '</span>' +
				'<div class="an-bigscore"><b>' + e.score.toFixed(0) + '</b><small>/ 100</small></div>' +
				'<div class="an-bar"><span style="width:' + e.score + '%;background:' + (side === 'a' ? COL_A : COL_B) + '"></span></div>' +
				'<small class="an-muted">Rank #' + e.rank + ' of ' + emps.length + ' &middot; ' + e.tasks + ' tasks</small>';
		};

		var notes = function (e, side) {
			var li = function (arr, cls, icon) { return arr.map(function (s) { return '<li class="' + cls + '"><span class="fa ' + icon + '"></span>' + esc(s) + '</li>'; }).join(''); };
			return '<h4><span class="an-dot" style="background:' + (side === 'a' ? COL_A : COL_B) + '"></span>' + esc(e.name) + '</h4><ul>' +
				li(e.strengths, 'good', 'fa-check') + li(e.concerns, 'bad', 'fa-exclamation') +
				((e.strengths.length + e.concerns.length) ? '' : '<li class="an-muted">No notable strengths or concerns yet.</li>') + '</ul>';
		};

		var render = function () {
			var a = byId[selA.value], b = byId[selB.value];
			if (!a || !b) { return; }

			document.getElementById('cmp-prof-a').innerHTML = profile(a, 'a');
			document.getElementById('cmp-prof-b').innerHTML = profile(b, 'b');

			radar.data.datasets = [a, b].map(function (e, i) {
				var c = i ? COL_B : COL_A;
				return { label: e.name, data: AXES.map(function (x) { return e.components[x[0]] || 0; }), borderColor: c, backgroundColor: c + '2b', borderWidth: 2, pointRadius: 3, pointBackgroundColor: c };
			});
			radar.update();

			var wa = 0, wb = 0, rows = '';
			METRICS.forEach(function (m) {
				var va = m[1](a), vb = m[1](b);
				var win = va === vb ? '' : ((m[3] === 'high') === (va > vb) ? 'a' : 'b');
				if (win === 'a') { wa++; } else if (win === 'b') { wb++; }
				var max = Math.max(Math.abs(va), Math.abs(vb), 1);
				var bar = function (v, c) { return '<span class="an-mbar"><i style="width:' + Math.max(3, Math.abs(v) / max * 100) + '%;background:' + c + '"></i></span>'; };
				rows += '<div class="an-mrow">' +
					'<div class="an-mside a' + (win === 'a' ? ' win' : '') + '"><b>' + m[2](a) + '</b>' + bar(va, COL_A) + '</div>' +
					'<div class="an-mlabel">' + m[0] + (m[3] === 'low' ? '<small>lower is better</small>' : '') + '</div>' +
					'<div class="an-mside b' + (win === 'b' ? ' win' : '') + '"><b>' + m[2](b) + '</b>' + bar(vb, COL_B) + '</div>' +
					'</div>';
			});
			document.getElementById('cmp-rows').innerHTML = rows;

			var v = document.getElementById('cmp-verdict');
			var lead = wa === wb ? null : (wa > wb ? a : b);
			v.innerHTML = lead
				? '<b>' + esc(lead.name) + '</b> leads on <b>' + Math.max(wa, wb) + '</b> of ' + METRICS.length + ' measures (' + Math.min(wa, wb) + ' for ' + esc((lead === a ? b : a).name) + ').'
				: 'These two are evenly matched: ' + wa + ' measures each.';

			document.getElementById('cmp-notes-a').innerHTML = notes(a, 'a');
			document.getElementById('cmp-notes-b').innerHTML = notes(b, 'b');
		};

		// two different people only: if the same one is picked twice, move the other side
		var pickOther = function (not) { return emps.filter(function (e) { return e.id !== not; })[0].id; };
		selA.addEventListener('change', function () { if (selA.value === selB.value) { selB.value = pickOther(+selA.value); } render(); });
		selB.addEventListener('change', function () { if (selA.value === selB.value) { selA.value = pickOther(+selB.value); } render(); });

		// defaults: best vs lowest scoring, for the clearest first impression
		selA.value = emps[0].id;
		selB.value = emps[emps.length - 1].id;
		render();
		onShow.compare = function () { radar.resize(); };
	}

	/* ------------------------------------------------------------ start on the tab in the URL */
	var start = (location.hash || '').replace('#', '');
	show(panes[start] ? start : 'overview', false);
	// KPI cards link to tabs with #name; react to hash changes without a reload
	window.addEventListener('hashchange', function () {
		var n = (location.hash || '').replace('#', '');
		if (panes[n]) { show(n, false); window.scrollTo({ top: 0, behavior: 'smooth' }); }
	});
})();
