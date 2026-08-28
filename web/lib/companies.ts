import { pool } from "@/lib/db";

export type Company = {
  id: string;
  name: string;
  category: string;
  city: string;
  address: string | null;
  rating: number | null;
  reviews_count: number;
  site: string | null;
  phone: string | null;
};

export type CompanyQuery = {
  q?: string;
  city?: string;
  limit?: number;
};

const MAX_LIMIT = 200;

export async function listCities(): Promise<string[]> {
  const { rows } = await pool.query<{ city: string }>(
    "SELECT city FROM company GROUP BY city ORDER BY city",
  );
  return rows.map((row) => row.city);
}

export async function listCompanies({ q, city, limit = 50 }: CompanyQuery): Promise<{
  rows: Company[];
  total: number;
}> {
  const safeLimit = Math.min(Math.max(limit, 1), MAX_LIMIT);
  // Параметризованный запрос: значения не склеиваются в SQL.
  const params: (string | null)[] = [q?.trim() || null, city?.trim() || null];
  const where = `
    WHERE ($1::text IS NULL OR name ILIKE '%' || $1 || '%')
      AND ($2::text IS NULL OR city = $2)
  `;

  const [list, count] = await Promise.all([
    pool.query<Company>(
      `SELECT id, name, category, city, address, rating::float8 AS rating,
              reviews_count, site, phone
         FROM company
         ${where}
        ORDER BY reviews_count DESC, name
        LIMIT $3`,
      [...params, safeLimit],
    ),
    pool.query<{ total: string }>(`SELECT count(*) AS total FROM company ${where}`, params),
  ]);

  return { rows: list.rows, total: Number(count.rows[0]?.total ?? 0) };
}
