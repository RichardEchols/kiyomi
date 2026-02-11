/**
 * Kiyomi v5.0 Onboarding — 3-Step Setup
 * Step 1: Name + Preset
 * Step 2: Pick CLI
 * Step 3: Telegram Token
 */

let currentStep = 1;
let selectedCli = '';
let selectedPreset = '';
let presets = [];
let claimedToken = '';
let claimedUsername = '';

// Preset metadata (emoji + short description)
const PRESET_META = {
    'personal-assistant': { emoji: '🌸', desc: 'General-purpose helper for everyday tasks' },
    'law-firm':           { emoji: '⚖️', desc: 'Legal research, drafting, and case management' },
    'crypto-trader':      { emoji: '📈', desc: 'Market analysis, portfolio tracking, risk management' },
    'student':            { emoji: '📚', desc: 'Study guides, tutoring, exam prep' },
    'small-business':     { emoji: '🏪', desc: 'Marketing, invoicing, customer outreach' },
    'customer-service':   { emoji: '🎧', desc: 'Support templates, de-escalation, FAQs' },
};

// CLI metadata
const CLI_META = {
    'claude': { icon: '🟣', name: 'Claude', sub: 'Claude Max/Pro subscription ($20/mo)', priority: 1 },
    'codex':  { icon: '🟢', name: 'Codex', sub: 'ChatGPT Plus subscription ($20/mo)', priority: 2 },
    'gemini': { icon: '🔵', name: 'Gemini', sub: 'Google account (Free!)', priority: 3 },
};

// --- Step Navigation ---

function goToStep(step) {
    document.querySelectorAll('.step').forEach(el => el.classList.remove('active'));
    const target = step === 'done' ? 'step-done' : `step-${step}`;
    document.getElementById(target).classList.add('active');
    currentStep = step;

    if (step === 2) detectCLIs();
    if (step === 3) checkBotPool();
}

// --- Step 1: Name + Preset ---

async function loadPresets() {
    try {
        const res = await fetch('/api/presets');
        const data = await res.json();
        presets = data.presets || [];
    } catch (e) {
        console.error('Failed to load presets:', e);
        presets = [];
    }

    const grid = document.getElementById('preset-grid');
    // Add a "Custom" option
    const allOptions = [
        ...presets.map(p => ({
            id: p.id,
            title: p.title.replace('Kiyomi — ', ''),
            content: p.content,
        })),
        { id: 'custom', title: 'Custom', content: '' }
    ];

    grid.innerHTML = allOptions.map(p => {
        const meta = PRESET_META[p.id] || { emoji: '✏️', desc: 'Write your own instructions' };
        return `
            <div class="preset-card" data-preset="${p.id}" onclick="selectPreset('${p.id}')">
                <div class="preset-emoji">${meta.emoji}</div>
                <div class="preset-name">${p.title}</div>
                <div class="preset-desc">${meta.desc}</div>
            </div>
        `;
    }).join('');

    // Auto-select personal assistant
    if (presets.length > 0) {
        selectPreset('personal-assistant');
    }
}

function selectPreset(id) {
    selectedPreset = id;
    document.querySelectorAll('.preset-card').forEach(el => {
        el.classList.toggle('selected', el.dataset.preset === id);
    });

    const editor = document.getElementById('identity-editor');
    if (id === 'custom') {
        editor.value = '';
        editor.placeholder = 'Describe what you want your assistant to do...';
        editor.focus();
    } else {
        const preset = presets.find(p => p.id === id);
        if (preset) {
            editor.value = preset.content;
        }
    }

    validateStep1();
}

function validateStep1() {
    const name = document.getElementById('user-name').value.trim();
    const hasIdentity = document.getElementById('identity-editor').value.trim().length > 0;
    document.getElementById('btn-step1-next').disabled = !name || !hasIdentity;
}

// --- Step 2: CLI Detection ---

async function detectCLIs() {
    const list = document.getElementById('cli-list');
    list.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-hint);">Detecting installed CLIs...</div>';

    try {
        const res = await fetch('/api/cli/status');
        const data = await res.json();
        const providers = data.providers || {};

        // Build CLI cards
        const cliOrder = ['claude', 'codex', 'gemini'];
        let html = '';
        let anyInstalled = false;
        let bestCli = '';

        for (const cli of cliOrder) {
            // Map provider keys — detect_all() returns bare names (claude, codex, gemini)
            const info = providers[cli] || providers[`${cli}-cli`] || {};
            const installed = info.installed || false;
            const meta = CLI_META[cli];

            if (installed && !bestCli) bestCli = cli;
            if (installed) anyInstalled = true;

            const badgeClass = installed ? 'installed' : 'missing';
            const badgeText = installed ? 'Installed' : 'Not Found';
            const unavailableClass = installed ? '' : 'unavailable';

            html += `
                <div class="cli-card ${unavailableClass}" data-cli="${cli}" onclick="${installed ? `selectCli('${cli}')` : ''}">
                    <div class="cli-icon">${meta.icon}</div>
                    <div class="cli-info">
                        <div class="cli-name">${meta.name}</div>
                        <div class="cli-sub">${meta.sub}</div>
                    </div>
                    <div class="cli-badge ${badgeClass}">${badgeText}</div>
                </div>
            `;
        }

        list.innerHTML = html;
        document.getElementById('no-cli-help').style.display = anyInstalled ? 'none' : 'block';

        // Auto-select best available
        if (bestCli) {
            selectCli(bestCli);
        }

    } catch (e) {
        console.error('CLI detection failed:', e);
        list.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-hint);">Could not detect CLIs. Make sure Kiyomi is running.</div>';
    }
}

async function selectCli(cli) {
    selectedCli = cli;
    document.querySelectorAll('.cli-card').forEach(el => {
        el.classList.toggle('selected', el.dataset.cli === cli);
    });

    // Check if this CLI is authenticated — if not, trigger OAuth
    try {
        const res = await fetch('/api/cli/status');
        const data = await res.json();
        const info = data.providers?.[cli] || {};

        if (info.installed && !info.authenticated) {
            // CLI installed but not authenticated — trigger OAuth
            const authSection = document.getElementById('cli-auth-section');
            if (authSection) {
                const meta = CLI_META[cli] || {};
                authSection.innerHTML = `
                    <div style="text-align: center; margin-top: 16px; padding: 16px; background: rgba(255,255,255,0.05); border-radius: 12px;">
                        <p style="font-size: 14px; color: var(--text-secondary); margin-bottom: 12px;">
                            ${meta.name || cli} needs to be signed in with your ${meta.sub || 'subscription'}.
                        </p>
                        <button class="pool-btn" id="btn-cli-auth" onclick="triggerCliAuth('${cli}')">
                            Sign In to ${meta.name || cli}
                        </button>
                        <div id="cli-auth-result" style="margin-top: 8px; font-size: 13px; color: var(--text-hint);"></div>
                    </div>
                `;
                authSection.style.display = 'block';
            }
            // Allow proceeding even without auth (they can auth later)
            document.getElementById('btn-step2-next').disabled = false;
        } else {
            // Already authenticated or not installed — hide auth section
            const authSection = document.getElementById('cli-auth-section');
            if (authSection) {
                authSection.style.display = 'none';
            }
            document.getElementById('btn-step2-next').disabled = false;
        }
    } catch (e) {
        console.error('CLI status check failed:', e);
        document.getElementById('btn-step2-next').disabled = false;
    }
}

async function triggerCliAuth(cli) {
    const btn = document.getElementById('btn-cli-auth');
    const result = document.getElementById('cli-auth-result');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Opening sign-in...';
    }
    if (result) result.textContent = 'A browser window should open. Sign in with your account.';

    try {
        const res = await fetch('/api/cli/auth', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider: cli, force: true }),
        });
        const data = await res.json();

        if (data.launched) {
            if (result) result.innerHTML = '<span style="color: #4ade80;">Sign-in started! Complete it in your browser, then continue.</span>';
        } else {
            if (result) result.innerHTML = `<span style="color: #4ade80;">${data.detail || 'Already signed in!'}</span>`;
        }
    } catch (e) {
        console.error('CLI auth failed:', e);
        if (result) result.textContent = 'Auth failed. You can sign in later via Terminal.';
    }

    if (btn) {
        btn.disabled = false;
        btn.textContent = 'Try Again';
    }
}

// --- Step 3: Telegram ---

async function checkBotPool() {
    const poolSection = document.getElementById('pool-section');
    try {
        const res = await fetch('/api/telegram/pool');
        const data = await res.json();

        if (data.has_bots) {
            poolSection.innerHTML = `
                <div style="text-align: center; margin-bottom: 20px;">
                    <p style="font-size: 15px; color: var(--text-secondary); margin-bottom: 12px;">
                        We have a pre-made bot ready for you!
                    </p>
                    <button class="pool-btn" onclick="claimBot()">
                        Claim Instant Bot
                    </button>
                    <div id="claimed-result"></div>
                </div>
                <div class="or-claim">— or create your own below —</div>
            `;
        } else {
            poolSection.innerHTML = '';
        }
    } catch (e) {
        poolSection.innerHTML = '';
    }
}

async function claimBot() {
    const name = document.getElementById('user-name').value.trim() || 'User';
    try {
        const res = await fetch('/api/telegram/claim', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        });
        const data = await res.json();

        if (data.status === 'ok') {
            claimedToken = data.token;
            claimedUsername = data.username;
            document.getElementById('claimed-result').innerHTML = `
                <div class="claimed-info">
                    <span class="claimed-name">@${data.username}</span> claimed!
                    <br>Token saved automatically.
                </div>
            `;
            // Auto-fill and enable finish
            document.getElementById('telegram-token').value = data.token;
            document.getElementById('btn-finish').disabled = false;
        } else {
            document.getElementById('claimed-result').innerHTML = `
                <div style="color: var(--text-hint); margin-top: 8px; font-size: 13px;">
                    No bots available. Create one manually below.
                </div>
            `;
        }
    } catch (e) {
        console.error('Claim failed:', e);
    }
}

function validateTelegram() {
    const token = document.getElementById('telegram-token').value.trim();
    // Basic validation: should contain a colon
    document.getElementById('btn-finish').disabled = !token.includes(':');
}

// --- Finish: Save Everything ---

async function finishSetup() {
    const btn = document.getElementById('btn-finish');
    btn.disabled = true;
    btn.textContent = 'Setting up...';

    const name = document.getElementById('user-name').value.trim();
    const identityContent = document.getElementById('identity-editor').value.trim();
    const token = document.getElementById('telegram-token').value.trim();

    try {
        // 1. Save identity file
        await fetch('/api/identity', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: identityContent }),
        });

        // 2. Save config
        const config = {
            name: name,
            cli: selectedCli,
            telegram_token: token,
            telegram_user_id: '',
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'America/New_York',
            model: '',
            setup_complete: true,
        };

        const res = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        });

        const data = await res.json();
        if (data.status === 'ok') {
            // Extract bot username for Telegram link
            const botUsername = claimedUsername || '';
            if (botUsername) {
                document.getElementById('telegram-link').href = `https://t.me/${botUsername}`;
            } else {
                document.getElementById('telegram-link').href = 'https://telegram.org';
            }
            goToStep('done');
        } else {
            btn.disabled = false;
            btn.textContent = 'Finish Setup';
            alert('Setup failed: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        console.error('Setup error:', e);
        btn.disabled = false;
        btn.textContent = 'Finish Setup';
        alert('Setup failed: ' + e.message);
    }
}

// --- Event Listeners ---

document.addEventListener('DOMContentLoaded', () => {
    // Load presets
    loadPresets();

    // Step 1 validation
    document.getElementById('user-name').addEventListener('input', validateStep1);
    document.getElementById('identity-editor').addEventListener('input', validateStep1);

    // Step 1 next
    document.getElementById('btn-step1-next').addEventListener('click', () => goToStep(2));

    // Step 2 next
    document.getElementById('btn-step2-next').addEventListener('click', () => goToStep(3));

    // Step 3 validation
    document.getElementById('telegram-token').addEventListener('input', validateTelegram);

    // Finish
    document.getElementById('btn-finish').addEventListener('click', finishSetup);
});
