# Design: Mobile App Backend Integration

## Technical Approach

Refactor `QuantLabRepository` from an in-memory mock singleton into a facade over Retrofit + Moshi (remote) and Room (local cache). The ViewModel retains its existing `StateFlow` surface so Compose screens remain unchanged. Phase 1 adds read-only network sync, CORS on Flask, and an offline-first fallback.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Retrofit + Moshi vs Ktor Client | Moshi already in build.gradle.kts; matches existing codegen setup | **Retrofit + Moshi** |
| Room vs DataStore for cache | Need relational caching of campaigns, pipeline runs, stats with timestamps | **Room** |
| Single repository singleton vs DI | Minimal churn; existing code already uses `QuantLabRepository.instance` | **Keep singleton, refactor internals** |
| UiState as new top-level API vs backward-compatible wrappers | Preserve existing screens exactly | **Keep existing `StateFlow` properties; add internal `UiState` orchestration** |
| Base URL source | Must support dev vs prod without rebuild | **BuildConfig field + .env override via secrets plugin** |
| Network on main thread prevention | Coroutines already used in ViewModel | **Repository exposes `suspend` functions; ViewModel calls from `viewModelScope`** |

## Data Flow

    Screen (Compose) ──collectAsState()──▶ ViewModel StateFlow
                                                │
                                          ViewModel calls repository
                                                │
                                    ┌───────────┴────────────┐
                                    ▼                        ▼
                              Retrofit API              Room DAO
                                    │                        │
                                    │   cache on success     │
                                    └───────────┬────────────┘
                                                ▼
                                         Repository facade
                                        (returns UiState internally,
                                         updates backward-compatible StateFlows)

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `app/src/main/java/com/example/data/remote/ApiService.kt` | Create | Retrofit GET endpoints for health, campaigns, pipeline, stats |
| `app/src/main/java/com/example/data/remote/NetworkModule.kt` | Create | Retrofit + OkHttp client with logging interceptor, 10s connect/read timeouts, `BuildConfig.BASE_URL` from Gradle buildConfigField |
| `app/src/main/java/com/example/data/remote/model/ApiModels.kt` | Create | Moshi models with `@Json(name = "...")` for snake_case → camelCase mapping |
| `app/src/main/java/com/example/data/local/QuantLabDatabase.kt` | Create | Room database (`.db` file, fallbackToDestructiveMigration=false) with entities: CampaignEntity, PipelineRunEntity, StatsEntity, HealthEntity |
| `app/src/main/java/com/example/data/local/dao/*.kt` | Create | DAOs: `campaignDao`, `pipelineDao`, `statsDao`, `healthDao`; queries use `fetchedAt` timestamp |
| `app/src/main/java/com/example/data/repository/QuantLabRepository.kt` | Modify | Replace in-memory mocks with API + Room orchestration; keep singleton `instance` |
| `app/src/main/java/com/example/ui/QuantLabViewModel.kt` | Modify | Add internal `UiState` collection; preserve existing `StateFlow` outputs for screens |
| `app/src/main/java/com/example/data/model/UiState.kt` | Create | Sealed class: `Loading`, `Success(data)`, `Error(message)` |
| `app/src/main/res/xml/network_security_config.xml` | Create | Allow cleartext HTTP for dev base URL (10.0.2.2, 10.0.3.2, 172.16.0.0/12, 127.0.0.1) |
| `app/src/main/AndroidManifest.xml` | Modify | Attach `network_security_config` via `android:networkSecurityConfig` |
| `sdk/quantlab/dashboard/app.py` | Modify | Add `flask-cors` with mobile dev origin + GET methods |

## Interfaces / Contracts

```kotlin
// Repository contract (Phase 1 — read-only)
suspend fun getSystemHealth(): UiState<SystemHealth>
suspend fun getCampaigns(): UiState<List<Campaign>>
suspend fun getCampaign(id: String): UiState<Campaign>
suspend fun getPipelineRuns(): UiState<List<PipelineRun>>
suspend fun getStats(): UiState<Stats>

// Backward-compatible ViewModel surface preserved
val campaigns: StateFlow<List<Campaign>>
val systemHealth: StateFlow<SystemHealth>
```

```python
# Flask CORS contract
# Must respond with Access-Control-Allow-Origin for mobile dev origin
# Must allow GET methods for /api/*
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Repository API/Room orchestration, error mapping to UiState | JUnit + MockWebServer (mock Retrofit responses) |
| Unit | ViewModel StateFlow unwrapping from UiState | JUnit + Turbine or manual StateFlow testing |
| Integration | Room DAO + database migrations | Robolectric + Room testing |
| Unit | Flask CORS headers | Flask test client with Origin header assertions |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

1. Add network security config for dev cleartext HTTP (localhost/emulator).
2. Introduce `NetworkModule` + `ApiService` with build-time base URL.
3. Add Room database + entities; run migration on first launch.
4. Refactor `QuantLabRepository` internals to call API, cache results to Room, and fall back to cache on failure. Keep singleton `instance`.
5. ViewModel adds `viewModelScope.launch` to trigger initial data loads; existing `StateFlow` emissions stay unchanged.
6. Enable Flask CORS for mobile dev origin; verify `/api/health` from emulator.

No data migration needed. Existing mock data remains as initial Room seed if cache is empty.

## Open Questions

- [ ] Confirm mobile dev origin hostname/IP (e.g., `10.0.2.2` for emulator, or LAN IP).
- [ ] Verify Flask backend `/api/campaigns` JSON shape vs `Models.kt` data classes; may need Moshi `@Json(name=...)` mappings.
