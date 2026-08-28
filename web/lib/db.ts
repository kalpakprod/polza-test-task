import { Pool } from "pg";

// Один пул на процесс. В dev Next перезагружает модули, поэтому кладём в globalThis,
// иначе на каждом HMR утекает новый пул соединений.
const globalForPool = globalThis as unknown as { pgPool?: Pool };

function createPool(): Pool {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error("DATABASE_URL is not set (see env.example)");
  }
  return new Pool({ connectionString, max: 5 });
}

export const pool: Pool = globalForPool.pgPool ?? createPool();

if (process.env.NODE_ENV !== "production") {
  globalForPool.pgPool = pool;
}
