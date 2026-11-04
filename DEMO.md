# Northwind click-through

Start the stack, then load the fictional library:

```bash
docker compose up --build
python scripts/load_dataset.py
```



The app is at http://localhost:5173. The API is at http://localhost:8000. Every demo account uses `ChangeMe123!`.

Use two browser sessions so the accounts stay signed in at the same time. Each tab keeps its own session.

1. Sign in as `eng.employee@northwind.example`. Open Documents. Salary bands and Leave policy are absent. On-call guide and Office hours are listed.
2. Search for `salary bands`. The HR document is not in the results. Search for `on-call` and open the engineering guide.
3. Ask “What are the confidential HR salary bands?” The answer does not include the salary text.
4. Paste the Salary bands id from `dataset/manifest.json` onto `/documents/{id}`. Download is refused and the file is not saved.
5. Sign in as `hr.manager@northwind.example` in the other session. Documents shows the HR library and the upload form is locked to HR. Engineering is not available as a destination.
6. Sign in as `admin@northwind.example`. People lists every account. Audit shows the denied download. Grants on a document accept an email and can be revoked.

Indexing and live answers need `OPENROUTER_API_KEY` in `.env`, then `docker compose up -d api worker`. Open a failed document and choose Retry indexing. Until that key is set, chat and search explain that the key is missing. Download permission still applies.
