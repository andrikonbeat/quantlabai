# Tasks: Mobile App Backend Integration

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~900 (520 new + 380 modified) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Foundation + API client → PR 2: Cache + Repository → PR 3: ViewModel + UI → PR 4: Testing |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Flask CORS + network security + Retrofit/Moshi client | PR 1 | `./gradlew test` (ApiService + NetworkModule) | Flask dev server + emulator `/api/health` | Revert `sdk/quantlab/dashboard/app.py`, `network_security_config.xml`, `data/remote/` |
| 2 | Room entities/DAOs + Repository facade refactor | PR 2 | `./gradlew test` (Repository + DAO) | Room in-memory DB + MockWebServer | Revert `data/local/` and `QuantLabRepository.kt` |
| 3 | UiState + ViewModel + Dashboard/Campaigns wiring | PR 3 | `./gradlew test` (ViewModel + screens) | Compose preview + emulator navigation | Revert `UiState.kt`, `QuantLabViewModel.kt`, `DashboardScreen.kt`, `CampaignsScreen.kt` |
| 4 | Error/loading states + contract tests + Flask CORS pytest | PR 4 | `./gradlew test` + Flask `pytest` | pytest + Compose UI test | Revert test additions and UI state branches |

## Phase 1: Backend Foundation (parallelizable)

- [x] 1.1 Enable `flask-cors` in `sdk/quantlab/dashboard/app.py` for mobile dev origin with GET methods
- [x] 1.2 Create `app/src/main/res/xml/network_security_config.xml` allowing cleartext HTTP for `10.0.2.2`, `10.0.3.2`, `127.0.0.1`
- [x] 1.3 Register `android:networkSecurityConfig` in `app/src/main/AndroidManifest.xml`

## Phase 2: API Client

- [x] 2.1 Create `app/src/main/java/com/example/data/remote/model/ApiModels.kt` with Moshi `@Json(name=...)` mappings for Flask `/api/*` JSON shapes
- [x] 2.2 Create `app/src/main/java/com/example/data/remote/ApiService.kt` with Retrofit GET endpoints: `/api/health`, `/api/campaigns`, `/api/campaigns/{id}`, `/api/pipeline`, `/api/stats`
- [x] 2.3 Create `app/src/main/java/com/example/data/remote/NetworkModule.kt` with Retrofit + OkHttp (10s timeouts, logging interceptor, `BuildConfig.BASE_URL`)

## Phase 3: Offline Cache

- [x] 3.1 Create Room entities: `CampaignEntity`, `PipelineRunEntity`, `StatsEntity`, `HealthEntity` with `fetchedAt` timestamp
- [x] 3.2 Create DAOs: `CampaignDao`, `PipelineDao`, `StatsDao`, `HealthDao` with `@Query` accessors using `fetchedAt`
- [x] 3.3 Create `app/src/main/java/com/example/data/local/QuantLabDatabase.kt` (fallbackToDestructiveMigration=false)

## Phase 4: Repository + ViewModel

- [x] 4.1 Create `app/src/main/java/com/example/data/model/UiState.kt` sealed class: `Loading`, `Success(data)`, `Error(message)`
- [x] 4.2 Add `PipelineRun` and `Stats` domain models to `data/model/Models.kt`
- [x] 4.3 Refactor `QuantLabRepository.kt` to suspend `UiState<T>` functions; API-first, cache on success, fallback to cache on failure; preserve singleton `instance`
- [ ] 4.4 Update `QuantLabViewModel.kt` with internal `UiState` orchestration; preserve existing `StateFlow` outputs for screens

## Phase 5: UI Wiring

- [ ] 5.1 Update `DashboardScreen.kt` to show loading/error states; replace hardcoded metrics with live health/stats
- [ ] 5.2 Update `CampaignsScreen.kt` to trigger repository load and show loading/error states

## Phase 6: Testing

- [ ] 6.1 Write `ApiService` + `NetworkModule` unit tests with MockWebServer (RED: network failure → Error; GREEN: 200 → Success)
- [ ] 6.2 Write Repository tests for error mapping (malformed JSON → Error, offline → cache fallback)
- [ ] 6.3 Write Room DAO + migration tests with Robolectric
- [ ] 6.4 Write Flask CORS pytest asserting `Access-Control-Allow-Origin` for mobile origin on `/api/health`
- [ ] 6.5 Run `./gradlew test` and `./gradlew assembleDebug`; verify zero `ui/theme/` changes
