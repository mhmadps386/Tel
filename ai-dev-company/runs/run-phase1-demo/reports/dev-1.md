Added task priorities (low/medium/high, default medium), status/priority filters on GET /api/tasks, a new GET /api/stats endpoint and matching dashboard UI, with 17 new node:test cases; all 24 tests pass.

## Files changed
- ai-dev-company/demo-app/src/store.js: PRIORITIES/STATUSES constants, validatePriority(); create() takes `priority` (default "medium"); update() validates title/done/priority before mutating anything; list(filters) with validated status/priority; new stats().
- ai-dev-company/demo-app/src/app.js: readFilters() passes `status`/`priority` query params to store.list(); new GET /api/stats route.
- ai-dev-company/demo-app/public/index.html: summary cards (Total/Open/Done + High/Medium/Low) populated from /api/stats; priority <select> (default Medium) in the add form; priority badge on each task.
- ai-dev-company/demo-app/test/priority.test.js (new): API + store unit coverage.

Commit 54ed2c9 on branch aidc/run-phase1-demo/dev-1 (local only, not pushed).

## Behaviour
- POST /api/tasks: `priority` optional, defaults to "medium"; any value other than "low"/"medium"/"high" (incl. null, numbers, wrong case, "") -> 400 ValidationError.
- PATCH /api/tasks/:id: `priority` may be changed; invalid value -> 400. A rejected PATCH no longer partially applies other fields (previously a valid title could be saved before an invalid `done` was rejected).
- GET /api/tasks?status=open|done&priority=low|medium|high: either or both, ANDed. Unknown or empty values -> 400. No filters -> all tasks (unchanged).
- GET /api/stats -> {"total","open","done","byPriority":{"low","medium","high"}}, all integers, all keys present even when empty.

## Tests run
Command: `npm test` (in ai-dev-company/demo-app)
Output: `# tests 24`, `# pass 24`, `# fail 0`, `# cancelled 0`, `# skipped 0` (7 existing + 17 new).

## Known limitations
- Unknown query parameter *names* (e.g. ?foo=bar) are ignored; only unknown *values* of status/priority are rejected. Repeated params (?status=open&status=done) use the first value.
- Dashboard has no filter UI (not in scope) and its tests are static HTML assertions, not browser-driven.
- Pre-existing: a JSON body of `null` on POST/PATCH yields 500 rather than 400 (not changed).

RESULT: PASS
