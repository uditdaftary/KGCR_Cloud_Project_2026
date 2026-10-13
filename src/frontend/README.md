# Frontend

Two things live here.

## The dashboard

`index.html`, `app.js`, `plot.js` and `app.css` are the single-page dashboard served by
`kgcr dashboard` (server, SQLite store and job runner in
[../backend/kgcr/dashboard/](../backend/kgcr/dashboard/)).

```
kgcr dashboard --open
```

Vanilla JS modules, no build step and no dependencies. Every figure is read from the JSON API,
which reads the committed reports, the artifact store and the local database. The fonts
(Archivo, Martian Mono) are self-hosted under `fonts/` with their SIL Open Font License texts,
pinned from fontsource (`@fontsource-variable/archivo@5.2.8`,
`@fontsource-variable/martian-mono@5.2.7`), so the page works offline.

The design system is recorded in [../../DESIGN.md](../../DESIGN.md).

## The static results page

`build_dashboard.py` writes `results/dashboard.html`, a static offline view over
`results/*.json` that can be attached to the submission. It has no JavaScript.

```
python src/frontend/build_dashboard.py
```
