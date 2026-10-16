# Related-record loading audit

Targeted inspection on 2026-10-13, based on main `175cb1fd`; this is not a whole-repository performance audit or production benchmark.

## Organization regression — PR #926

- Before: construction loaded memberships and fetched each user individually. Public rendering did not need them, but a stale reference raised `User not found` and broke the page.
- Now: constructing or serializing an organization does not load members. First access loads memberships and users in one batch; subsequent accesses reuse the instance cache. `init_members()` remains an explicit refresh and membership mutations refresh the cache.
- Admin organization details use that same loader, including membership IDs for existing row actions. Missing users are skipped without deleting records or granting access. Invalid user deserialization still raises.
- Organization serialization excludes member caches; authoritative memberships remain in their existing collection. Input dictionaries are copied rather than mutated.
- Query contract: the anonymous public organization-data path has one organization lookup and no member-loading queries. Member loading has one membership query and at most one user query, independent of member count. Session/authorization queries and cursor network batches are not included.
- Focused tests exercise real Flask routes/database reads, lazy loading, query counts, cache refresh, orphan records, roles/permissions, admin membership IDs and serialization.

## Other verified constructor lookups — not changed in #926

| Code | Verified behavior | Next bounded investigation |
|---|---|---|
| `utils/classes/Organizer.py`, `Organizer` / `OrganizingEntity` | Linked organizations are fetched during construction to hydrate displayed fields. | Measure repeated organization lookups on list/detail routes; batch hydration where those fields are actually required. Preserve privacy flags and live organization metadata. |
| `utils/classes/Demonstration.py` | Recurring children fetch the parent to populate repeat schedule / parent metadata. | Trace required parent fields and batch parents for list rendering. Preserve recurrence and public visibility contracts; do not simply drop the lookup. |
| `utils/classes/AdminActivity.py` | Construction fetches the actor, and serialization uses actor data. | Trace current callers, deleted-actor behavior and serialization consumers before separating actor loading from construction. Retain history without exposing sensitive user fields. |

Use explicit query/hydration boundaries for new read paths, avoid hidden constructor I/O, and return only necessary fields where the consuming model supports projection. On-demand loading alone does not fix a loop that accesses every relationship; batch those related reads. Do not introduce global caches for permission-sensitive records or change authorization checks as a performance shortcut.
