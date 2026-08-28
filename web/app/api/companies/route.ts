import { NextResponse } from "next/server";
import { listCompanies } from "@/lib/companies";

// Route Handler на тот же слой данных: та же выборка, но в JSON.
export async function GET(request: Request) {
  const url = new URL(request.url);
  const limitParam = Number(url.searchParams.get("limit") ?? 50);
  const { rows, total } = await listCompanies({
    q: url.searchParams.get("q") ?? undefined,
    city: url.searchParams.get("city") ?? undefined,
    limit: Number.isFinite(limitParam) ? limitParam : 50,
  });
  return NextResponse.json({ total, count: rows.length, items: rows });
}
