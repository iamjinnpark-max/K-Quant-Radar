import { randomUUID } from "node:crypto";

// In-memory stand-ins for Postgres and Redis so the full HTTP flows can be
// exercised by `node --test` without live services. The pg fake implements
// exactly the parameterized statements the source uses -- an unknown
// statement throws, so a new query cannot silently pass untested.

const normalize = (text) => text.replace(/\s+/g, " ").trim();

export function createFakeDb() {
  const authUsers = new Map(); // id -> row
  const resets = []; // { user_id, token_hash, expires_at }
  const verifications = [];
  const appUsers = new Map(); // cognito_sub -> true

  const byEmail = (email) =>
    [...authUsers.values()].find((row) => row.email === email) || null;

  async function query(text, params = []) {
    const sql = normalize(text);

    if (sql === "SELECT 1") {
      return { rowCount: 1, rows: [{ "?column?": 1 }] };
    }

    if (sql.startsWith("INSERT INTO auth_users")) {
      if (byEmail(params[0])) {
        return { rowCount: 0, rows: [] };
      }
      const row = {
        id: randomUUID(),
        email: params[0],
        password_hash: params[1],
        created_at: new Date(),
        updated_at: new Date(),
        email_verified_at: null,
      };
      authUsers.set(row.id, row);
      return { rowCount: 1, rows: [{ ...row }] };
    }

    if (sql.startsWith("SELECT id, email, password_hash, created_at, email_verified_at FROM auth_users WHERE email")) {
      const row = byEmail(params[0]);
      return { rowCount: row ? 1 : 0, rows: row ? [{ ...row }] : [] };
    }
    if (sql.startsWith("SELECT id, email, created_at, email_verified_at FROM auth_users WHERE id")) {
      const row = authUsers.get(params[0]);
      return { rowCount: row ? 1 : 0, rows: row ? [{ ...row }] : [] };
    }
    if (sql.startsWith("SELECT id, email, email_verified_at FROM auth_users WHERE id")) {
      const row = authUsers.get(params[0]);
      return { rowCount: row ? 1 : 0, rows: row ? [{ ...row }] : [] };
    }
    if (sql.startsWith("SELECT id, password_hash FROM auth_users WHERE id")) {
      const row = authUsers.get(params[0]);
      return { rowCount: row ? 1 : 0, rows: row ? [{ ...row }] : [] };
    }
    if (sql.startsWith("SELECT id FROM auth_users WHERE email")) {
      const row = byEmail(params[0]);
      return { rowCount: row ? 1 : 0, rows: row ? [{ id: row.id }] : [] };
    }

    if (sql.startsWith("INSERT INTO auth_email_verifications")) {
      verifications.push({
        user_id: params[0],
        token_hash: params[1],
        expires_at: new Date(Date.now() + params[2] * 1000),
      });
      return { rowCount: 1, rows: [] };
    }
    if (sql.startsWith("DELETE FROM auth_email_verifications WHERE user_id")) {
      const removed = removeWhere(verifications, (t) => t.user_id === params[0]);
      return { rowCount: removed, rows: [] };
    }
    if (sql.startsWith("DELETE FROM auth_email_verifications WHERE token_hash")) {
      const matches = verifications.filter(
        (t) => t.token_hash === params[0] && t.expires_at > new Date(),
      );
      removeWhere(verifications, (t) => t.token_hash === params[0] && t.expires_at > new Date());
      return {
        rowCount: matches.length,
        rows: matches.map((t) => ({ user_id: t.user_id })),
      };
    }
    if (sql.startsWith("DELETE FROM auth_email_verifications WHERE expires_at")) {
      const removed = removeWhere(verifications, (t) => t.expires_at <= new Date());
      return { rowCount: removed, rows: [] };
    }
    if (sql.startsWith("UPDATE auth_users SET email_verified_at")) {
      const row = authUsers.get(params[0]);
      if (row && row.email_verified_at == null) {
        row.email_verified_at = new Date();
      }
      return { rowCount: row ? 1 : 0, rows: [] };
    }

    if (sql.startsWith("INSERT INTO auth_password_resets")) {
      resets.push({
        user_id: params[0],
        token_hash: params[1],
        expires_at: new Date(Date.now() + params[2] * 1000),
      });
      return { rowCount: 1, rows: [] };
    }
    if (sql.startsWith("DELETE FROM auth_password_resets WHERE token_hash")) {
      const matches = resets.filter(
        (t) => t.token_hash === params[0] && t.expires_at > new Date(),
      );
      removeWhere(resets, (t) => t.token_hash === params[0] && t.expires_at > new Date());
      return {
        rowCount: matches.length,
        rows: matches.map((t) => ({ user_id: t.user_id })),
      };
    }
    if (sql.startsWith("DELETE FROM auth_password_resets WHERE user_id")) {
      const removed = removeWhere(resets, (t) => t.user_id === params[0]);
      return { rowCount: removed, rows: [] };
    }
    if (sql.startsWith("DELETE FROM auth_password_resets WHERE expires_at")) {
      const removed = removeWhere(resets, (t) => t.expires_at <= new Date());
      return { rowCount: removed, rows: [] };
    }
    if (sql.startsWith("UPDATE auth_users SET password_hash")) {
      const row = authUsers.get(params[1]);
      if (row) {
        row.password_hash = params[0];
      }
      return { rowCount: row ? 1 : 0, rows: [] };
    }

    if (sql.startsWith("SELECT to_regclass('public.users')")) {
      return { rowCount: 1, rows: [{ t: "users" }] };
    }
    if (sql.startsWith("DELETE FROM users WHERE cognito_sub")) {
      const removed = appUsers.delete(params[0]) ? 1 : 0;
      return { rowCount: removed, rows: [] };
    }
    if (sql.startsWith("DELETE FROM auth_users WHERE id")) {
      const removed = authUsers.delete(params[0]) ? 1 : 0;
      return { rowCount: removed, rows: [] };
    }

    if (sql === "BEGIN" || sql === "COMMIT" || sql === "ROLLBACK") {
      return { rowCount: 0, rows: [] };
    }

    throw new Error(`fake db has no handler for: ${sql}`);
  }

  return {
    query,
    async connect() {
      return { query, release() {} };
    },
    tables: { authUsers, resets, verifications, appUsers },
  };
}

function removeWhere(list, predicate) {
  let removed = 0;
  for (let i = list.length - 1; i >= 0; i -= 1) {
    if (predicate(list[i])) {
      list.splice(i, 1);
      removed += 1;
    }
  }
  return removed;
}

export function createFakeRedis() {
  const store = new Map(); // key -> { value, expiresAt|null }
  const sets = new Map(); // key -> Set

  const live = (key) => {
    const entry = store.get(key);
    if (!entry) {
      return null;
    }
    if (entry.expiresAt !== null && entry.expiresAt <= Date.now()) {
      store.delete(key);
      return null;
    }
    return entry;
  };

  return {
    store,
    sets,
    async ping() {
      return "PONG";
    },
    async get(key) {
      const entry = live(key);
      return entry ? entry.value : null;
    },
    async set(key, value, options = {}) {
      store.set(key, {
        value,
        expiresAt: options.EX ? Date.now() + options.EX * 1000 : null,
      });
      return "OK";
    },
    async expire(key, seconds) {
      const entry = live(key);
      if (!entry) {
        return 0;
      }
      entry.expiresAt = Date.now() + seconds * 1000;
      return 1;
    },
    async ttl(key) {
      const entry = live(key);
      if (!entry) {
        return -2;
      }
      if (entry.expiresAt === null) {
        return -1;
      }
      return Math.ceil((entry.expiresAt - Date.now()) / 1000);
    },
    async del(keys) {
      const list = Array.isArray(keys) ? keys : [keys];
      let removed = 0;
      for (const key of list) {
        if (store.delete(key)) {
          removed += 1;
        }
        if (sets.delete(key)) {
          removed += 1;
        }
      }
      return removed;
    },
    async incr(key) {
      const entry = live(key);
      const next = entry ? Number(entry.value) + 1 : 1;
      store.set(key, {
        value: String(next),
        expiresAt: entry ? entry.expiresAt : null,
      });
      return next;
    },
    async sAdd(key, member) {
      if (!sets.has(key)) {
        sets.set(key, new Set());
      }
      sets.get(key).add(member);
      return 1;
    },
    async sRem(key, member) {
      return sets.get(key)?.delete(member) ? 1 : 0;
    },
    async sMembers(key) {
      return [...(sets.get(key) ?? [])];
    },
  };
}
