import { listCities, listCompanies } from "@/lib/companies";

export const dynamic = "force-dynamic";

type SearchParams = Promise<{ q?: string; city?: string }>;

export default async function CompaniesPage({ searchParams }: { searchParams: SearchParams }) {
  const { q = "", city = "" } = await searchParams;
  // Данные читаются на сервере: Server Component обращается к Postgres напрямую,
  // в браузер уходит только готовая разметка.
  const [{ rows, total }, cities] = await Promise.all([
    listCompanies({ q, city, limit: 50 }),
    listCities(),
  ]);

  return (
    <main>
      <h1>Компании</h1>
      <p className="muted">
        Найдено {total}, показаны первые {rows.length}. Источник: таблица <code>company</code>.
      </p>

      <form className="filters" action="/companies" method="get">
        <input
          type="search"
          name="q"
          defaultValue={q}
          placeholder="Поиск по названию"
          aria-label="Поиск по названию"
        />
        <select name="city" defaultValue={city} aria-label="Фильтр по городу">
          <option value="">Все города</option>
          {cities.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <button type="submit">Показать</button>
        {(q || city) && (
          <a className="reset" href="/companies">
            Сбросить
          </a>
        )}
      </form>

      <div className="table-wrap">
        {rows.length === 0 ? (
          <p className="empty">Ничего не найдено. Попробуйте изменить запрос или город.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Название</th>
                <th>Категория</th>
                <th>Город</th>
                <th className="num">Рейтинг</th>
                <th className="num">Отзывы</th>
                <th>Сайт</th>
                <th>Телефон</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((company) => (
                <tr key={company.id}>
                  <td className="name">{company.name}</td>
                  <td>{company.category}</td>
                  <td>{company.city}</td>
                  <td className="num">{company.rating ?? "—"}</td>
                  <td className="num">{company.reviews_count}</td>
                  <td>
                    {company.site ? (
                      <a href={company.site} target="_blank" rel="noreferrer noopener">
                        {new URL(company.site).hostname}
                      </a>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>{company.phone ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </main>
  );
}
