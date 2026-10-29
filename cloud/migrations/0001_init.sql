-- Job-search agent engine, online search: initial schema.
-- Author: manpmanp <manp.node@gmail.com>. Generated with Claude (Anthropic). MIT.
CREATE TABLE IF NOT EXISTS config (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS postings (
  key TEXT PRIMARY KEY, url TEXT, title TEXT, employer TEXT, location TEXT, category TEXT, seniority TEXT,
  announced TEXT, deadline TEXT, arrangement TEXT, skills TEXT, status TEXT DEFAULT 'New', notes TEXT,
  description TEXT, source TEXT, found TEXT, norm TEXT, lead INTEGER DEFAULT 0, detail TEXT,
  updated_at TEXT
);
CREATE INDEX IF NOT EXISTS postings_url ON postings(url);
CREATE INDEX IF NOT EXISTS postings_norm ON postings(norm);
CREATE TABLE IF NOT EXISTS decisions (key TEXT PRIMARY KEY, decision TEXT, reasons TEXT, note TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT, mode TEXT, started TEXT, finished TEXT, summary TEXT);
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, kind TEXT, payload TEXT, state TEXT DEFAULT 'pending',
  attempts INTEGER DEFAULT 0, result TEXT, created_at TEXT, claimed_at INTEGER
);
CREATE INDEX IF NOT EXISTS tasks_state ON tasks(state, id);
CREATE TABLE IF NOT EXISTS log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, line TEXT);
CREATE TABLE IF NOT EXISTS robots (origin TEXT PRIMARY KEY, rules TEXT, fetched_at INTEGER);
CREATE TABLE IF NOT EXISTS logins (ip TEXT PRIMARY KEY, failures INTEGER, first_at INTEGER);
