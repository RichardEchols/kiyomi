/* Kiyomi Life Dashboard — Client */

(function () {
    'use strict';

    const API_URL = '/api/dashboard/data';

    // Category icon map
    const CAT_ICONS = {
        identity: '\uD83E\uDEB6',   // id card
        family: '\uD83D\uDC68\u200D\uD83D\uDC69\u200D\uD83D\uDC67\u200D\uD83D\uDC66',
        work: '\uD83D\uDCBC',
        health: '\uD83C\uDFE5',
        preferences: '\u2B50',
        goals: '\uD83C\uDFAF',
        schedule: '\uD83D\uDCC5',
        other: '\uD83D\uDCDD',
    };

    // ── Greeting ──────────────────────────────────
    function getGreeting(name) {
        var h = new Date().getHours();
        var base;
        if (h < 12) base = 'Good morning';
        else if (h < 17) base = 'Good afternoon';
        else base = 'Good evening';
        return name ? base + ', ' + name : base;
    }

    // ── Helpers ───────────────────────────────────
    function el(tag, cls, html) {
        var e = document.createElement(tag);
        if (cls) e.className = cls;
        if (html !== undefined) e.innerHTML = html;
        return e;
    }

    function truncate(str, max) {
        if (!str) return '';
        return str.length > max ? str.slice(0, max) + '\u2026' : str;
    }

    // ── Card Builders ─────────────────────────────

    function renderMemory(container, data) {
        var mem = data.memory || {};
        var cats = mem.categories || {};
        var total = mem.total_facts || 0;
        var convos = mem.conversations_this_week || 0;

        var html = '';
        html += '<div class="card-header">';
        html += '  <div class="card-title-row">';
        html += '    <div class="card-icon blue">\uD83E\uDDE0</div>';
        html += '    <span class="card-title">Memory</span>';
        html += '  </div>';
        html += '  <span class="card-badge blue">' + total + ' facts</span>';
        html += '</div>';

        if (total === 0) {
            html += emptyState('\uD83E\uDDE0', 'No memories yet', 'Chat with Kiyomi and she\'ll start remembering.');
        } else {
            // Stats row
            html += '<div class="stat-row">';
            html += '  <div class="stat-block"><div class="stat-value blue">' + total + '</div><div class="stat-label">Total Facts</div></div>';
            html += '  <div class="stat-block"><div class="stat-value blue">' + convos + '</div><div class="stat-label">Chats This Week</div></div>';
            html += '  <div class="stat-block"><div class="stat-value blue">' + Object.keys(cats).filter(function(k) { return cats[k].count > 0; }).length + '</div><div class="stat-label">Categories</div></div>';
            html += '</div>';

            // Category tiles
            html += '<div class="cat-grid">';
            var order = ['identity', 'family', 'work', 'health', 'preferences', 'goals', 'schedule', 'other'];
            for (var i = 0; i < order.length; i++) {
                var key = order[i];
                var cat = cats[key] || { name: key, count: 0 };
                var icon = CAT_ICONS[key] || '\uD83D\uDCCC';
                html += '<div class="cat-tile">';
                html += '  <span class="cat-tile-icon">' + icon + '</span>';
                html += '  <span class="cat-tile-count">' + cat.count + '</span>';
                html += '  <span class="cat-tile-name">' + (cat.name || key) + '</span>';
                html += '</div>';
            }
            html += '</div>';
        }

        container.innerHTML = html;
    }

    function renderTasks(container, data) {
        var tasks = data.tasks || {};
        var openTasks = tasks.open || [];
        var completedTasks = tasks.completed || [];
        var openCount = tasks.open_count || 0;
        var doneCount = tasks.completed_count || 0;

        var html = '';
        html += '<div class="card-header">';
        html += '  <div class="card-title-row">';
        html += '    <div class="card-icon red">\u2705</div>';
        html += '    <span class="card-title">Tasks</span>';
        html += '  </div>';
        if (openCount > 0) {
            html += '  <span class="card-badge red">' + openCount + ' open</span>';
        }
        html += '</div>';

        if (openCount === 0 && doneCount === 0) {
            html += emptyState('\u2705', 'No tasks yet', 'Tell Kiyomi to add a task for you.');
        } else {
            // Stats
            html += '<div class="stat-row">';
            html += '  <div class="stat-block"><div class="stat-value red">' + openCount + '</div><div class="stat-label">Open</div></div>';
            html += '  <div class="stat-block"><div class="stat-value green">' + doneCount + '</div><div class="stat-label">Completed</div></div>';
            html += '</div>';

            // Open tasks list (up to 8)
            if (openTasks.length > 0) {
                html += '<div class="section-label">Open</div>';
                html += '<div class="item-list">';
                var shown = openTasks.slice(0, 8);
                for (var i = 0; i < shown.length; i++) {
                    var t = shown[i];
                    var pri = t.priority || 'medium';
                    var isOverdue = t.due && new Date(t.due) < new Date();
                    html += '<div class="item-row">';
                    html += '  <span class="item-dot ' + pri + '"></span>';
                    html += '  <span class="item-text">' + escapeHtml(truncate(t.text, 60)) + '</span>';
                    if (t.due) {
                        html += '  <span class="item-meta' + (isOverdue ? ' overdue' : '') + '">' + formatDate(t.due) + '</span>';
                    } else {
                        html += '  <span class="priority-tag ' + pri + '">' + pri + '</span>';
                    }
                    html += '</div>';
                }
                html += '</div>';
                if (openTasks.length > 8) {
                    html += '<div style="text-align:center; margin-top:8px;"><span class="item-meta">+' + (openTasks.length - 8) + ' more</span></div>';
                }
            }
        }

        container.innerHTML = html;
    }

    function renderHealth(container, data) {
        var health = data.health || {};

        var html = '';
        html += '<div class="card-header">';
        html += '  <div class="card-title-row">';
        html += '    <div class="card-icon green">\uD83D\uDC9A</div>';
        html += '    <span class="card-title">Health</span>';
        html += '  </div>';
        html += '</div>';

        // Check if there's any health data
        var hasData = false;
        var meds = health.medications || [];
        var vitals = health.vitals || [];
        var appointments = health.appointments || [];
        var conditions = health.conditions || [];

        if (meds.length || vitals.length || appointments.length || conditions.length) {
            hasData = true;
        }

        // Also check if it's the skills data format (general array)
        var general = health.general || [];
        if (general.length) {
            hasData = true;
        }

        if (!hasData && Object.keys(health).length === 0) {
            html += emptyState('\uD83D\uDC9A', 'No health data yet', 'Tell Kiyomi about your medications, vitals, or appointments.');
        } else if (!hasData && general.length > 0) {
            // Skills format — show what's there
            html += '<div class="item-list">';
            for (var i = 0; i < general.length && i < 5; i++) {
                var item = general[i];
                html += '<div class="item-row">';
                html += '  <span class="item-dot low"></span>';
                html += '  <span class="item-text">' + escapeHtml(item.message || item.intent || 'Health data') + '</span>';
                html += '</div>';
            }
            html += '</div>';
        } else {
            // Medications
            if (meds.length) {
                html += '<div class="section-label">Medications</div>';
                html += '<div class="item-list">';
                for (var i = 0; i < meds.length && i < 5; i++) {
                    html += '<div class="item-row">';
                    html += '  <span class="item-dot low"></span>';
                    html += '  <span class="item-text">' + escapeHtml(typeof meds[i] === 'string' ? meds[i] : meds[i].name || '') + '</span>';
                    html += '</div>';
                }
                html += '</div>';
            }

            // Vitals
            if (vitals.length) {
                html += '<div class="card-divider"></div>';
                html += '<div class="section-label">Latest Vitals</div>';
                html += '<div class="item-list">';
                var latest = vitals.slice(-3);
                for (var i = 0; i < latest.length; i++) {
                    var v = latest[i];
                    html += '<div class="item-row">';
                    html += '  <span class="item-text">' + escapeHtml(typeof v === 'string' ? v : (v.type || '') + ': ' + (v.value || '')) + '</span>';
                    html += '</div>';
                }
                html += '</div>';
            }

            // Appointments
            if (appointments.length) {
                html += '<div class="card-divider"></div>';
                html += '<div class="section-label">Appointments</div>';
                html += '<div class="item-list">';
                for (var i = 0; i < appointments.length && i < 3; i++) {
                    var a = appointments[i];
                    html += '<div class="item-row">';
                    html += '  <span class="item-dot medium"></span>';
                    html += '  <span class="item-text">' + escapeHtml(typeof a === 'string' ? a : a.description || '') + '</span>';
                    if (a.date) html += '  <span class="item-meta">' + formatDate(a.date) + '</span>';
                    html += '</div>';
                }
                html += '</div>';
            }
        }

        container.innerHTML = html;
    }

    function renderBudget(container, data) {
        var budget = data.budget || {};

        var html = '';
        html += '<div class="card-header">';
        html += '  <div class="card-title-row">';
        html += '    <div class="card-icon orange">\uD83D\uDCB0</div>';
        html += '    <span class="card-title">Budget</span>';
        html += '  </div>';
        html += '</div>';

        var general = budget.general || [];
        var transactions = budget.transactions || [];
        var income = budget.income || 0;
        var expenses = budget.expenses || 0;

        if (Object.keys(budget).length === 0) {
            html += emptyState('\uD83D\uDCB0', 'No budget data yet', 'Tell Kiyomi about income and expenses to start tracking.');
        } else if (general.length > 0) {
            // Financial intelligence skill format
            for (var i = 0; i < general.length; i++) {
                var item = general[i];
                if (item.message) {
                    html += '<div class="item-row">';
                    html += '  <span class="item-text" style="white-space:normal;">' + escapeHtml(item.message) + '</span>';
                    html += '</div>';
                }
            }
        } else {
            // Standard budget format
            if (income || expenses) {
                var net = income - expenses;
                html += '<div class="stat-row">';
                html += '  <div class="stat-block"><div class="stat-value green">$' + formatMoney(income) + '</div><div class="stat-label">Income</div></div>';
                html += '  <div class="stat-block"><div class="stat-value red">$' + formatMoney(expenses) + '</div><div class="stat-label">Expenses</div></div>';
                html += '  <div class="stat-block"><div class="stat-value ' + (net >= 0 ? 'green' : 'red') + '">$' + formatMoney(Math.abs(net)) + '</div><div class="stat-label">Net</div></div>';
                html += '</div>';
            }

            if (transactions.length > 0) {
                html += '<div class="section-label">Recent</div>';
                html += '<div class="item-list">';
                var recent = transactions.slice(-5).reverse();
                for (var i = 0; i < recent.length; i++) {
                    var tx = recent[i];
                    var isIncome = (tx.type === 'income' || tx.amount > 0);
                    html += '<div class="txn-row">';
                    html += '  <span class="txn-desc">' + escapeHtml(tx.description || tx.name || '') + '</span>';
                    html += '  <span class="txn-amount ' + (isIncome ? 'income' : 'expense') + '">' + (isIncome ? '+' : '-') + '$' + formatMoney(Math.abs(tx.amount || 0)) + '</span>';
                    html += '</div>';
                }
                html += '</div>';
            }
        }

        container.innerHTML = html;
    }

    function renderHabits(container, data) {
        var habits = data.habits || {};

        var html = '';
        html += '<div class="card-header">';
        html += '  <div class="card-title-row">';
        html += '    <div class="card-icon yellow">\uD83D\uDD25</div>';
        html += '    <span class="card-title">Habits</span>';
        html += '  </div>';
        html += '</div>';

        var habitList = habits.habits || [];
        if (Array.isArray(habits)) habitList = habits;

        if (!habitList.length && Object.keys(habits).length === 0) {
            html += emptyState('\uD83D\uDD25', 'No habits tracked yet', 'Tell Kiyomi to track a habit for you.');
        } else if (habitList.length > 0) {
            html += '<div class="item-list">';
            for (var i = 0; i < habitList.length; i++) {
                var h = habitList[i];
                var name = typeof h === 'string' ? h : (h.name || h.habit || '');
                var streak = h.streak || 0;
                var todayDone = h.today || h.completed_today || false;
                html += '<div class="habit-row">';
                html += '  <span class="habit-status">' + (todayDone ? '\u2705' : '\u2B1C') + '</span>';
                html += '  <span class="habit-name">' + escapeHtml(name) + '</span>';
                if (streak > 0) {
                    html += '  <span class="habit-streak">\uD83D\uDD25 ' + streak + '</span>';
                }
                html += '</div>';
            }
            html += '</div>';
        } else {
            // Object format — iterate keys
            html += '<div class="item-list">';
            var keys = Object.keys(habits);
            for (var i = 0; i < keys.length; i++) {
                var key = keys[i];
                var val = habits[key];
                html += '<div class="habit-row">';
                html += '  <span class="habit-status">\uD83D\uDD25</span>';
                html += '  <span class="habit-name">' + escapeHtml(key) + '</span>';
                if (typeof val === 'number') {
                    html += '  <span class="habit-streak">' + val + '</span>';
                }
                html += '</div>';
            }
            html += '</div>';
        }

        container.innerHTML = html;
    }

    function renderRelationships(container, data) {
        var rels = data.relationships || {};

        var html = '';
        html += '<div class="card-header">';
        html += '  <div class="card-title-row">';
        html += '    <div class="card-icon pink">\uD83D\uDC96</div>';
        html += '    <span class="card-title">Relationships</span>';
        html += '  </div>';
        html += '</div>';

        var people = rels.people || rels.contacts || [];
        if (Array.isArray(rels)) people = rels;

        if (!people.length && Object.keys(rels).length === 0) {
            html += emptyState('\uD83D\uDC96', 'No relationships yet', 'Tell Kiyomi about the people in your life.');
        } else if (people.length > 0) {
            html += '<div class="item-list">';
            for (var i = 0; i < people.length && i < 8; i++) {
                var p = people[i];
                var name = typeof p === 'string' ? p : (p.name || '');
                var type = p.relationship || p.type || '';
                var initial = name ? name.charAt(0).toUpperCase() : '?';
                html += '<div class="person-row">';
                html += '  <div class="person-avatar">' + initial + '</div>';
                html += '  <div class="person-info">';
                html += '    <div class="person-name">' + escapeHtml(name) + '</div>';
                if (type) html += '    <div class="person-detail">' + escapeHtml(type) + '</div>';
                if (p.birthday) html += '    <div class="person-detail">\uD83C\uDF82 ' + escapeHtml(p.birthday) + '</div>';
                html += '  </div>';
                html += '</div>';
            }
            html += '</div>';
        } else {
            // Object format
            html += '<div class="item-list">';
            var keys = Object.keys(rels);
            for (var i = 0; i < keys.length && i < 8; i++) {
                var key = keys[i];
                html += '<div class="person-row">';
                html += '  <div class="person-avatar">' + key.charAt(0).toUpperCase() + '</div>';
                html += '  <div class="person-info"><div class="person-name">' + escapeHtml(key) + '</div></div>';
                html += '</div>';
            }
            html += '</div>';
        }

        container.innerHTML = html;
    }

    function renderReminders(container, data) {
        var rems = data.reminders || {};

        var html = '';
        html += '<div class="card-header">';
        html += '  <div class="card-title-row">';
        html += '    <div class="card-icon teal">\u23F0</div>';
        html += '    <span class="card-title">Reminders</span>';
        html += '  </div>';
        html += '</div>';

        var list = rems.reminders || rems.active || [];
        if (Array.isArray(rems)) list = rems;

        if (!list.length && Object.keys(rems).length === 0) {
            html += emptyState('\u23F0', 'No reminders set', 'Ask Kiyomi to remind you about something.');
        } else if (list.length > 0) {
            html += '<div class="item-list">';
            for (var i = 0; i < list.length && i < 8; i++) {
                var r = list[i];
                var text = typeof r === 'string' ? r : (r.text || r.message || r.description || '');
                var time = r.time || r.fire_time || r.datetime || '';
                var recurring = r.recurring || r.repeat || false;
                html += '<div class="reminder-row">';
                html += '  <span class="reminder-icon">' + (recurring ? '\uD83D\uDD01' : '\uD83D\uDD14') + '</span>';
                html += '  <div class="reminder-info">';
                html += '    <div class="reminder-text">' + escapeHtml(truncate(text, 60)) + '</div>';
                if (time) html += '    <div class="reminder-time">' + escapeHtml(formatDateTime(time)) + '</div>';
                html += '  </div>';
                if (recurring) html += '  <span class="reminder-type">Recurring</span>';
                html += '</div>';
            }
            html += '</div>';
        } else {
            // Object format
            var keys = Object.keys(rems);
            html += '<div class="item-list">';
            for (var i = 0; i < keys.length && i < 8; i++) {
                html += '<div class="reminder-row">';
                html += '  <span class="reminder-icon">\uD83D\uDD14</span>';
                html += '  <div class="reminder-info"><div class="reminder-text">' + escapeHtml(keys[i]) + '</div></div>';
                html += '</div>';
            }
            html += '</div>';
        }

        container.innerHTML = html;
    }

    // ── Utility ───────────────────────────────────

    function emptyState(icon, title, hint) {
        return '<div class="empty-state">' +
            '<div class="empty-icon">' + icon + '</div>' +
            '<div class="empty-text">' + escapeHtml(title) + '</div>' +
            '<div class="empty-hint">' + escapeHtml(hint) + '</div>' +
            '</div>';
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function formatDate(dateStr) {
        try {
            var d = new Date(dateStr);
            if (isNaN(d.getTime())) return dateStr;
            var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            return months[d.getMonth()] + ' ' + d.getDate();
        } catch (e) {
            return dateStr;
        }
    }

    function formatDateTime(dateStr) {
        try {
            var d = new Date(dateStr);
            if (isNaN(d.getTime())) return dateStr;
            var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            var hours = d.getHours();
            var ampm = hours >= 12 ? 'PM' : 'AM';
            hours = hours % 12 || 12;
            var mins = d.getMinutes();
            return months[d.getMonth()] + ' ' + d.getDate() + ' at ' + hours + ':' + (mins < 10 ? '0' : '') + mins + ' ' + ampm;
        } catch (e) {
            return dateStr;
        }
    }

    function formatMoney(n) {
        if (!n && n !== 0) return '0';
        return Number(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    }

    // ── Main fetch + render ───────────────────────

    function loadDashboard() {
        var btn = document.getElementById('btn-refresh');
        if (btn) btn.classList.add('spinning');

        fetch(API_URL)
            .then(function (res) { return res.json(); })
            .then(function (data) {
                // Greeting
                var name = (data.config && data.config.name) || '';
                document.getElementById('greeting').textContent = getGreeting(name);

                // Render cards
                renderMemory(document.getElementById('card-memory'), data);
                renderTasks(document.getElementById('card-tasks'), data);
                renderHealth(document.getElementById('card-health'), data);
                renderBudget(document.getElementById('card-budget'), data);
                renderHabits(document.getElementById('card-habits'), data);
                renderRelationships(document.getElementById('card-relationships'), data);
                renderReminders(document.getElementById('card-reminders'), data);

                // Updated time
                var now = new Date();
                var hours = now.getHours();
                var ampm = hours >= 12 ? 'PM' : 'AM';
                hours = hours % 12 || 12;
                var mins = now.getMinutes();
                document.getElementById('last-updated').textContent =
                    'Updated ' + hours + ':' + (mins < 10 ? '0' : '') + mins + ' ' + ampm;
            })
            .catch(function (err) {
                console.error('Dashboard fetch error:', err);
            })
            .finally(function () {
                if (btn) {
                    setTimeout(function () { btn.classList.remove('spinning'); }, 600);
                }
            });
    }

    // ── Init ──────────────────────────────────────

    document.addEventListener('DOMContentLoaded', function () {
        loadDashboard();

        document.getElementById('btn-refresh').addEventListener('click', function () {
            // Re-trigger animations
            var cards = document.querySelectorAll('.card');
            for (var i = 0; i < cards.length; i++) {
                cards[i].style.animation = 'none';
                cards[i].offsetHeight; // trigger reflow
                cards[i].style.animation = '';
            }
            loadDashboard();
        });

        // Auto-refresh every 5 minutes
        setInterval(loadDashboard, 5 * 60 * 1000);
    });
})();
