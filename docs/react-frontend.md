# Incremental React frontend

The public frontend remains Flask/Jinja. React owns individual explicitly marked
regions, starting with the volunteer form on `/kampanja/`. The header, campaign
content, fundraising page, newsletter, admin and authentication stay in their
existing implementation. No SPA router or JavaScript server runtime is required.

## Develop and build

Use Node 22.12+ (Node 22 LTS is used in CI) and the existing Python environment:

```sh
npm ci
npm run build
# Run Flask as usual, in a separate terminal:
npm run dev
```

`dev` watches sources and rebuilds the same static files Flask serves. Refresh
the Flask page after a rebuild. There is deliberately no second origin, HMR
server, CORS configuration or authentication proxy. `npm run typecheck` checks
TypeScript without writing files. Run `npm run build` before committing; watch
output is not a substitute for the final checked production build.

Vite writes hashed assets and `manifest.json` to
`mielenosoitukset_fi/static/frontend/`. **Commit that directory with the source
and package-lock.json.** This is an intentional bridge to the existing git-based
Python deployment and Docker image: both already include these static files and
need no Node installation at runtime or on the production server. The existing
test workflow builds from the lockfile, type-checks and rejects stale or extra
generated files. Do not edit the generated JavaScript manually. `node_modules`
is excluded from Git and Docker contexts.

This adds approximately 70 KB gzipped on the campaign page, including React;
other pages do not load it. Revisit artifact delivery through CI if the frontend
grows enough that committing builds becomes burdensome. Assets use relative
internal imports and Flask-generated static URLs, so a static URL prefix is
supported. Future entries can share dependencies through Vite's chunk graph.

## Add another island

1. Write a typed component under `frontend/src/components/` and a page entry
   under `frontend/src/entries/`. Import `vite/modulepreload-polyfill` and use
   `mountIsland` from `lib/mount-island.tsx` in the entry.
2. Add its entry to `frontend/vite.config.ts`. Keep unrelated page entries
   separate so visiting one page does not download every React screen.
3. Mark the owned region with `data-react-island="your-name"` and
   `data-props-id="your-config-id"`. Put props in an `application/json` script
   with that ID, serializing a Jinja dictionary using `tojson` (never `safe`).
4. Import `frontend_entry` from `_macros/frontend.html` and call it only on the
   consuming page with the manifest source key, such as
   `src/entries/volunteer.tsx`. The Flask resolver includes dependent CSS first.
5. Remove legacy event handlers that touch that region. React uses `createRoot`
   to replace its fallback; Jinja markup is not React hydration output.
6. Add meaningful browser checks for the workflow and follow the project's
   in-conversation visual acceptance process in both themes and widths.

Flask/Babel remains the translation source. Pass translated behavior messages
as JSON props instead of introducing a separate frontend translation catalog.
The initial form's labels remain Finnish, matching the existing `lang="fi"`
campaign section; its feedback retains the existing fi/en/sv translations.

## Volunteer form contract

The form posts the same trimmed `name`, `email`, `phone`, `city` and `notes`
JSON fields to the endpoint supplied by `url_for('campaign.add_volunteer')`.
Same-origin session cookies are included. Publication/login checks, validation,
database writes, confirmation tokens and queued email remain in Flask. Mounting
React grants no permission. Server rules must also be applied to the API.

The component owns feedback, invalid-field markers, first-invalid focus and
pending state. A synchronous ref prevents simultaneous submissions; controls
are disabled while a request is pending. Failed requests retain entered values;
successful signups clear the form and ask the user to confirm by email. Server
error text is rendered as plain React text, never HTML. Non-JSON responses and
login redirects are failures, not successful signups.

The existing disabled Jinja form is a deliberate no-JavaScript/load-failure
fallback inside the island, with the same fields and IDs. It has no submit
handler and must remain disabled. A loading/contact notice remains visible if
the module fails to load; `noscript` also explains that nothing was sent. Keep
this small fallback aligned with field changes in the React component. No other
script may enable it. A render failure restores the disabled fallback.

The static recovery exporter can keep campaign/collection information in its
server-rendered HTML while removing interactive forms and scripts. A working
React signup is not promised on a static recovery copy.

Reference: [Vite's backend integration](https://vite.dev/guide/backend-integration).
