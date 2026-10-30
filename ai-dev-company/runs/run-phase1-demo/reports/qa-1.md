PASS: dev-1 (commit 54ed2c9) meets all five spec requirements; all 24 tests pass, there are no regressions, and only low-severity issues were found.

## Tests run
- `npm test` in demo-app of the qa-1 worktree (Node v22.22.0): tests 24, suites 0, pass 24, fail 0, cancelled 0, skipped 0, todo 0.
- Pre-existing test file only, run against the new code: `node --test test/api.test.js` gave tests 7, pass 7, fail 0.
- Baseline `HEAD~1` test/api.test.js and test/helpers.js, extracted to a scratch dir and run against the new src/ and public/: tests 7, pass 7, fail 0. `git diff HEAD~1` shows that neither file was modified.

## Spec compliance
1. Priority field. **Met.** store.js:45 defaults to "medium". store.js:8-12 checks the value with an exact `includes` against `['low','medium','high']` on create (store.js:52) and on PATCH (store.js:75). Invalid values throw ValidationError, which the API returns as 400 (app.js:83). On PATCH every field is validated before any field is changed (store.js:67-78), so a rejected PATCH changes nothing. The probes confirmed this.
2. List filters. **Met.** app.js:40-46 reads `status` and `priority`. store.js:20-29 validates them, filters on them and combines them. An empty or unknown value returns 400. With no filters, all tasks are returned.
3. GET /api/stats. **Met.** store.js:31-39 and app.js:60-62 return `{total, open, done, byPriority:{low,medium,high}}`. All values are integers, and every key is present when the store is empty and after deletes.
4. Dashboard. **Met.** public/index.html: the summary cards (total, open, done and three priority cards) come from /api/stats. A `<select id="priority">` defaults to medium, is sent on POST and resets after submit. Each `<li>` shows a `priority priority-${t.priority}` badge.
5. Tests. **Met.** test/priority.test.js covers the default, valid and invalid priorities on create (including "HIGH", "", null, 3 and ["high"]), PATCH update, invalid PATCH with no partial save, each filter, combined filters, 400 for bad filters (including `status=` and `priority=`), the stats shape when empty and after PATCH and DELETE, the integer types, the dashboard wiring and the store unit rules. All pre-existing tests pass.

## Edge-case probes
Script: scratchpad/qa/probe.js. It requires the worktree's src/app.js and listens on port 0.
- POST priority "HIGH", "high ", {toString:"high"}, true and "constructor": each returns 400.
- PATCH `{done:true, priority:"HIGH"}`, `{done:"yes", priority:"high"}` and `{title:"", priority:"high"}`: each returns 400. A follow-up GET shows task 1 still `done:false, priority:"medium"`, so nothing was partly saved.
- PATCH /api/tasks/999 with a bad priority returns 404.
- `?status=`, `?priority=` and a bare `?status` each return 400. `?status=open&priority=high` returns the correct single task. `?status=%6Fpen` is decoded and works.
- `?priority=high&priority=bogus` returns 200, because only the first value is used. `?priority=bogus&priority=high` returns 400. `?status=open&status=done` returns open tasks only.
- `?priority[]=high`, `?Priority=bogus` and `?foo=bar` are treated as unknown keys and ignored, so all tasks are returned.
- Stats after marking a task done and then deleting tasks: the counts were correct at each step and went back to all zeros. `POST /api/stats` returns 404.
- A body of JSON `null` on POST or PATCH returns 500. The baseline HEAD~1 does the same (checked), so this was not introduced by this change.

## Bugs and regressions
- src/app.js:43, **low**. Repeated query parameters are not rejected: only the first value is validated and used, so `?priority=high&priority=bogus` returns 200. The spec does not cover repeated parameters. Suggested fix: use `searchParams.getAll(key)` and return 400 when there is more than one value.
- src/store.js:45 and :68, **low, pre-existing, not a regression**. A JSON body of `null` (or another non-object) on POST or PATCH causes a TypeError and a 500 instead of a 400. The baseline behaves the same way.
- src/app.js:40-46, **low/informational**. Unknown filter keys (for example `?Priority=`) are silently ignored. The spec only requires 400 for unknown values, so this is consistent with it.
- public/index.html, **low**. The add-task form does not show an error when the API rejects the request (also true of the baseline). The select only offers valid values, so in practice this cannot happen.
- No regressions found.

## Recommendation
Accept dev-1. Optionally, in a follow-up, reject repeated filter parameters and return 400 for non-object JSON bodies.

RESULT: PASS
