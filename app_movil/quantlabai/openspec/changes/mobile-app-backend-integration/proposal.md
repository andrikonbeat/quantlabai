# Proposal: Mobile App Backend Integration

## Intent

Connect the QuantLab AI mobile app from in-memory mocks to the live Flask backend. Preserve Graphite/ElectricCyan UI; change only the data layer.

## Scope

### In Scope
- Replace `QuantLabRepository` mocks with Retrofit + Room
- Connect read endpoints: `/api/health`, `/api/campaigns`, `/api/campaigns/{id}`, `/api/pipeline`, `/api/stats`
- Add `UiState` (Loading/Success/Error) to ViewModels
- Cache-first reads with offline fallback
- Enable Flask CORS for mobile origin

### Out of Scope
- Auth, writes, WebSocket, push
- New screens or theme changes
- Backend features beyond existing `/api/*`

## Capabilities

> Contract for sdd-spec.

### New
- `mobile-control-plane`: Mobile data layer (API client, Room cache, repository, ViewModel states, offline fallback)

### Modified
- None

## Approach

Incremental phases:
1. **Phase 1 — Read-only** (this change): Live reads + cache.
2. **Phase 2 — Offline**: Full Room sync + WorkManager.
3. **Phase 3 — Writes + Auth**: Backend writes + API key.
4. **Phase 4 — Real-time**: WebSocket + push.

Phase 1 is viable now because all needed endpoints already exist.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `data/repository/QuantLabRepository.kt` | Modified | API + cache replaces mocks |
| `data/remote/`, `data/local/` | New | Retrofit, Moshi, Room |
| `ui/QuantLabViewModel.kt` | Modified | Expose UiState |
| `ui/screens/DashboardScreen.kt` | Modified | Real health/stats |
| `ui/screens/CampaignsScreen.kt` | Modified | Real campaigns |
| `sdk/quantlab/dashboard/app.py` | Modified | CORS for mobile |
| `ui/theme/`, composables | Unchanged | Preserve aesthetic |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| CORS blocks mobile | Medium | `flask-cors` with explicit origin |
| Network on main thread | Low | Coroutines + repository abstraction |
| Backend schema drift | Low | Moshi adapters + contract tests |
| No auth exposes backend | Medium | Reverse proxy / firewall; API key in Phase 3 |

## Rollback Plan

Revert repository/ViewModel to mocks; remove new data packages; disable CORS. Single commit revert; screens stay functional.

## Dependencies

- Backend: `flask-cors` for mobile origin
- Backend: existing `/api/*` endpoints stable
- Deferred: `/api/reports/generate` review (Phase 2+)

## Success Criteria

- [ ] Dashboard, Campaigns, Stats, Pipeline show live data
- [ ] Offline fallback to cache
- [ ] `./gradlew test` passes
- [ ] `./gradlew assembleDebug` succeeds
- [ ] No `ui/theme/` or composable changes
- [ ] CORS enabled; health check 200 from mobile

## Estimated Effort

| Phase | Effort |
|-------|--------|
| Phase 1 — Read-only | 1–2 weeks |
| Phase 2 — Cache + Offline | 1 week |
| Phase 3 — Writes + Auth | 2–3 weeks |
| Phase 4 — Real-time | 1–2 weeks |

## Proposal question round

**Assumptions**: existing AGP/Kotlin setup supports new deps; backend CORS configured for dev; Phase 1 keeps backend schemas unchanged; mock fallback acceptable if API fails.

**Questions**:
1. Should Phase 1 consume `/api/reports/generate`, or defer report viewing?
2. Is offline-first required in Phase 1, or network-only with error state enough?
3. Should `mobile-control-plane` cover offline sync, or should sync be a separate capability?
4. Expose `MobileNotifierDispatcher` backend endpoint in Phase 1 for push readiness, or keep it strictly Phase 4?
