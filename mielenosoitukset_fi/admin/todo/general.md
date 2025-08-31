### **1. Functionality**

- [ ] Verify all analytics endpoints return correct data:

  * `/per_demo_analytics/<demo_id>` — check daily, weekly, per-minute calculations.
  * `/api/demos/recommendations` — check top demos scoring formula.
  * `/api/demos/nousussa` — ensure views in last 24h are accurate.
  * `/analytics/overall_24h` and `/api/analytics/overall_24h` — check interval rounding and timezone handling.
- [ ] Test `recommend_demos_no_user` scoring with multiple tags, empty analytics, or missing created\_at.
- [ ] Check `get_demo_views` and `count_per_demo` return the right aggregated format for templates.
- [ ] Validate `load_user()` works for all user types and handles deleted/invalid IDs gracefully.
- [ ] Test `get_admin_activity` pagination with >1 page of logs.
- [ ] Ensure `get_user_role_counts()` correctly handles missing or unexpected roles.
- [ ] MFA validation placeholder (`validate_mfa_token`) needs proper logic.

---

### **2. Security / Permissions**

- [ ] Ensure every route with `@admin_required` actually protects sensitive data.
- [ ] `/api/demos/recommendations` currently lacks admin or user permissions — consider restricting.
- [ ] Verify `api_demos_nousussa` enforces `@permission_required("VIEW_ANALYTICS")`.
- [ ] Escape all template-rendered values to prevent XSS (demo titles, analytics labels).
- [ ] MFA validation must be implemented before enabling sensitive endpoints in production.

---

### **3. UX / Admin Interface**

- [ ] Add pagination or filtering for `/logs` if many entries exist.
- [ ] Improve chart labels: currently per-minute charts are huge; maybe aggregate hourly for readability.
- [ ] Add tooltip or hover-over on analytics charts for detailed counts.
- [ ] Consider a “last updated” timestamp for analytics pages.
- [ ] Provide clear error messages for missing analytics (`abort(404)` is fine, but maybe flash\_message too).

---

### **4. Optimization / Cleanup**

- [ ] Remove duplicate imports (`datetime`, `timedelta`, `timezone`, `defaultdict`, `ObjectId` appear multiple times).
- [ ] Consolidate `demo_analytics` functions; there are multiple definitions of the same route name.
- [ ] Reuse logic for per-minute / per-day / per-week aggregations across endpoints.
- [ ] Consider caching analytics computations for high-traffic dashboards.
- [ ] Avoid fetching `mongo.demonstrations.find_one` repeatedly in loops (batch fetch or `$in` query).

---

### **5. Future Enhancements**

- [ ] Add admin filters for demos by category, trending score, or popularity directly in the UI.
- [ ] Provide CSV/PDF export for per-demo analytics.
- [ ] Integrate user-based recommendations later (`recommend_demos_no_user` is only for anonymous).
- [ ] Add timezone selection for admin dashboard analytics.
- [ ] Include alerts for unusual spikes in views or trending demos.