/**
 * Kiyomi SDK Bridge
 *
 * HTTP service providing multi-turn Claude Code sessions.
 * Uses claude CLI with --resume for session continuity.
 * Unlocks keychain before each call for LaunchAgent compatibility.
 *
 * Endpoints:
 *   POST /query          — Send a message (creates or resumes session)
 *   POST /session/new    — Create a fresh session
 *   GET  /session/:id    — Get session info
 *   GET  /sessions       — List all sessions
 *   DELETE /session/:id  — Delete a session
 *   GET  /health         — Health check
 */

import express from "express";
import { readFileSync, writeFileSync, existsSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { spawn } from "child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const app = express();
app.use(express.json({ limit: "10mb" }));

const PORT = parseInt(process.env.SDK_BRIDGE_PORT || "3456");
const SESSIONS_FILE = join(__dirname, "sessions.json");
const MAX_SESSION_AGE_MS = 24 * 60 * 60 * 1000; // 24 hours
const CLAUDE_PATH = process.env.CLAUDE_PATH || "/opt/homebrew/bin/claude";
const KEYCHAIN_PASSWORD = process.env.KEYCHAIN_PASSWORD || "";

// --- Session Store ---

function loadSessions() {
  try {
    if (existsSync(SESSIONS_FILE)) {
      return JSON.parse(readFileSync(SESSIONS_FILE, "utf-8"));
    }
  } catch (e) {
    console.error("Failed to load sessions:", e.message);
  }
  return {};
}

function saveSessions(sessions) {
  try {
    writeFileSync(SESSIONS_FILE, JSON.stringify(sessions, null, 2));
  } catch (e) {
    console.error("Failed to save sessions:", e.message);
  }
}

// userId -> { sessionId, createdAt, lastUsed, messageCount }
let sessions = loadSessions();

function cleanOldSessions() {
  const now = Date.now();
  let changed = false;
  for (const [userId, session] of Object.entries(sessions)) {
    if (now - session.lastUsed > MAX_SESSION_AGE_MS) {
      delete sessions[userId];
      changed = true;
      console.log(`Cleaned expired session for user ${userId}`);
    }
  }
  if (changed) saveSessions(sessions);
}

setInterval(cleanOldSessions, 30 * 60 * 1000);

// --- Core Query Handler ---

async function runQuery({ prompt, userId, cwd, maxTurns, systemPrompt, newSession, model }) {
  const startTime = Date.now();

  // Check for existing session to resume
  const existingSession = sessions[userId];
  const resumeId = (!newSession && existingSession?.sessionId) || undefined;

  if (resumeId) {
    console.log(`Resuming session ${resumeId} for user ${userId}`);
  } else {
    console.log(`Starting new session for user ${userId}`);
  }

  // Unlock keychain before spawning Claude
  try {
    const keychainPath = join(process.env.HOME, "Library/Keychains/login.keychain-db");
    const { execSync } = await import("child_process");
    execSync(`security unlock-keychain -p "${KEYCHAIN_PASSWORD}" "${keychainPath}"`, { stdio: "ignore" });
  } catch (e) {
    console.warn("Keychain unlock warning:", e.message);
  }

  // Build claude args as an array (no shell escaping needed)
  const args = [
    "-p", prompt,
    "--output-format", "json",
    "--dangerously-skip-permissions",
    "--max-turns", String(maxTurns || 50),
  ];

  if (model) {
    args.push("--model", model);
  }

  if (resumeId) {
    args.push("--resume", resumeId);
  }

  if (systemPrompt) {
    args.push("--system-prompt", systemPrompt);
  }

  return new Promise((resolve) => {
    let stdout = "";
    let stderr = "";

    const proc = spawn(CLAUDE_PATH, args, {
      cwd: cwd || process.env.HOME,
      stdio: ["ignore", "pipe", "pipe"],
      env: {
        ...process.env,
        PATH: `/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin`,
      },
    });

    proc.stdout.on("data", (data) => { stdout += data.toString(); });
    proc.stderr.on("data", (data) => { stderr += data.toString(); });

    proc.on("close", (code) => {
      if (code !== 0) {
        console.error(`Claude exited with code ${code}: ${stderr.substring(0, 300)}`);

        // If there's stdout despite error, try to use it
        if (stdout.trim()) {
          try {
            const parsed = JSON.parse(stdout.trim());
            if (parsed.result) {
              resolve(formatResult(parsed, userId, startTime));
              return;
            }
          } catch {}
          // Return raw text if not JSON
          resolve({
            success: true,
            result: stdout.trim().substring(0, 5000),
            cost: 0,
            duration: Date.now() - startTime,
            turns: 0,
          });
          return;
        }

        resolve({
          success: false,
          error: `Claude exited with code ${code}: ${stderr.substring(0, 200)}`,
        });
        return;
      }

      // Parse JSON output
      try {
        const parsed = JSON.parse(stdout.trim());
        resolve(formatResult(parsed, userId, startTime));
      } catch (e) {
        // Not JSON — return as plain text
        resolve({
          success: true,
          result: stdout.trim() || "Done.",
          cost: 0,
          duration: Date.now() - startTime,
          turns: 0,
        });
      }
    });

    proc.on("error", (err) => {
      console.error("Spawn error:", err.message);
      resolve({
        success: false,
        error: err.message,
      });
    });
  });
}

function formatResult(parsed, userId, startTime) {
  const sessionId = parsed.session_id || parsed.sessionId || null;
  const resultText = parsed.result || parsed.text || "";
  const cost = parsed.cost_usd || parsed.total_cost_usd || 0;
  const turns = parsed.num_turns || 0;

  // Update session store
  if (sessionId && userId) {
    const prev = sessions[userId] || { createdAt: Date.now(), messageCount: 0 };
    sessions[userId] = {
      sessionId,
      createdAt: prev.createdAt,
      lastUsed: Date.now(),
      messageCount: (prev.messageCount || 0) + 1,
    };
    saveSessions(sessions);
  }

  return {
    success: true,
    result: resultText || "Done.",
    sessionId,
    cost,
    duration: parsed.duration_ms || (Date.now() - startTime),
    turns,
    tokens: {
      input: parsed.usage?.input_tokens || 0,
      output: parsed.usage?.output_tokens || 0,
    },
  };
}

// --- Routes ---

app.post("/query", async (req, res) => {
  const {
    prompt,
    userId = "default",
    cwd,
    maxTurns,
    systemPrompt,
    newSession = false,
    model,
  } = req.body;

  if (!prompt) {
    return res.status(400).json({ success: false, error: "prompt is required" });
  }

  console.log(`[${new Date().toISOString()}] Query from ${userId} (model=${model || "default"}): ${prompt.substring(0, 100)}...`);

  try {
    const result = await runQuery({ prompt, userId, cwd, maxTurns, systemPrompt, newSession, model });
    res.json(result);
  } catch (err) {
    console.error("Unhandled error:", err);
    res.status(500).json({ success: false, error: err.message });
  }
});

app.post("/session/new", async (req, res) => {
  const { userId = "default" } = req.body;
  delete sessions[userId];
  saveSessions(sessions);
  res.json({ success: true, message: `Session cleared for ${userId}. Next query starts fresh.` });
});

app.get("/session/:userId", (req, res) => {
  const session = sessions[req.params.userId];
  if (!session) {
    return res.status(404).json({ exists: false });
  }
  res.json({ exists: true, ...session, age: Date.now() - session.createdAt, idle: Date.now() - session.lastUsed });
});

app.get("/sessions", (req, res) => {
  const list = Object.entries(sessions).map(([userId, s]) => ({
    userId, ...s, age: Date.now() - s.createdAt, idle: Date.now() - s.lastUsed,
  }));
  res.json(list);
});

app.delete("/session/:userId", (req, res) => {
  const existed = !!sessions[req.params.userId];
  delete sessions[req.params.userId];
  saveSessions(sessions);
  res.json({ deleted: existed });
});

app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    uptime: process.uptime(),
    sessions: Object.keys(sessions).length,
    port: PORT,
  });
});

// --- Start ---

app.listen(PORT, "127.0.0.1", () => {
  console.log(`Kiyomi SDK Bridge running on port ${PORT}`);
  console.log(`Sessions: ${Object.keys(sessions).length} active`);
  cleanOldSessions();
});
