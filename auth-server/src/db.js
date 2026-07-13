import pg from "pg";

import { config } from "./config.js";

// Every query in this service goes through pool.query(text, params) with
// positional placeholders -- no string interpolation into SQL, ever.
export const pool = new pg.Pool({
  connectionString: config.databaseUrl,
  max: 10,
});

export async function closeDb() {
  await pool.end();
}
