# Apply Progress: Mobile App Backend Integration

## Status
Ready for next batch (PR 1 complete, PR 2 pending)

## Completed Tasks (PR 1 — stacked-to-main slice)

| Task | Description | Status |
|------|-------------|--------|
| 1.1 | Enable flask-cors in `sdk/quantlab/dashboard/app.py` for mobile dev origin with GET methods | ✅ Complete |
| 1.2 | Create `app/src/main/res/xml/network_security_config.xml` allowing cleartext HTTP for `10.0.2.2`, `10.0.3.2`, `127.0.0.1` | ✅ Complete |
| 1.3 | Register `android:networkSecurityConfig` in `app/src/main/AndroidManifest.xml` | ✅ Complete |
| 2.1 | Create `app/src/main/java/com/example/data/remote/model/ApiModels.kt` with Moshi `@Json(name=...)` mappings | ✅ Complete |
| 2.2 | Create `app/src/main/java/com/example/data/remote/ApiService.kt` with Retrofit GET endpoints | ✅ Complete |
| 2.3 | Create `app/src/main/java/com/example/data/remote/NetworkModule.kt` with Retrofit + OkHttp | ✅ Complete |
| — | Update `QuantLabRepository.kt` to use Retrofit refresh (preparatory step for full 4.3) | ✅ Complete |

## Work Unit Evidence

| Evidence | Value |
|----------|-------|
| Focused test command and exact result | `pytest sdk/quantlab/dashboard/tests/test_cors.py` → 4 passed in 1.52s |
| Runtime harness command/scenario and exact result | N/A — Android test runner unavailable (no Gradle/OpenJDK installed in this environment). Flask dev server runtime harness pending environment setup. |
| Rollback boundary | Revert `sdk/quantlab/dashboard/app.py`, `network_security_config.xml`, `data/remote/`, `QuantLabRepository.kt`, `build.gradle.kts`, `AndroidManifest.xml` |

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `sdk/quantlab/dashboard/tests/test_cors.py` | Unit (pytest) | N/A (new) | ✅ 3 tests written → failed | ✅ All 4 tests passed | ✅ Added stats endpoint test | ✅ Clean |
| 1.2 | `NetworkSecurityConfigTest.kt` | Robolectric | N/A (new) | ✅ Written | ➖ Blocked (no test runner) | ➖ Single (XML is structural) | ➖ None needed |
| 1.3 | `AndroidManifestTest.kt` | Robolectric | N/A (new) | ✅ Written | ➖ Blocked (no test runner) | ➖ Single (manifest attr is structural) | ➖ None needed |
| 2.1 | `ApiModelsTest.kt` | Unit | N/A (new) | ✅ Written | ➖ Blocked (no test runner) | ✅ 4 cases (health, campaign, stats, detail) | ➖ None needed |
| 2.2 | `ApiServiceTest.kt` | MockWebServer | N/A (new) | ✅ Written | ➖ Blocked (no test runner) | ✅ 3 cases (health, campaigns, detail) | ➖ None needed |
| 2.3 | `NetworkModuleTest.kt` | Unit | N/A (new) | ✅ Written | ➖ Blocked (no test runner) | ➖ Single (module init is structural) | ➖ None needed |
| 4.3* | `QuantLabRepositoryTest.kt` | Unit + Fake API | N/A (new) | ✅ Written | ➖ Blocked (no test runner) | ✅ 4 cases (health, campaigns, failure, approveItem) | ➖ None needed |

## Test Summary
- **Total tests written**: 14
- **Total tests passing**: 4 (Flask CORS only)
- **Layers used**: Unit (pytest 4), Robolectric (3), MockWebServer (3), Fake API (4)
- **Infrastructure blocker**: Android test runner (`./gradlew test`) unavailable — no Gradle wrapper and no OpenJDK installed. Kotlin tests compile-only verified by inspection.
- **Pure functions created**: 0 (all logic is in repository/mapping layer)

## Remaining Tasks
- [ ] 3.1 Create Room entities: CampaignEntity, PipelineRunEntity, StatsEntity, HealthEntity
- [ ] 3.2 Create DAOs: CampaignDao, PipelineDao, StatsDao, HealthDao
- [ ] 3.3 Create QuantLabDatabase.kt
- [ ] 4.1 Create UiState.kt sealed class
- [ ] 4.2 Add PipelineRun and Stats domain models to Models.kt
- [ ] 4.3 Full repository refactor: suspend UiState functions, API-first, cache on success, fallback to cache on failure
- [ ] 4.4 Update QuantLabViewModel.kt with internal UiState orchestration
- [ ] 5.1 Update DashboardScreen.kt
- [ ] 5.2 Update CampaignsScreen.kt
- [ ] 6.1 Write ApiService + NetworkModule unit tests with MockWebServer
- [ ] 6.2 Write Repository tests
- [ ] 6.3 Write Room DAO + migration tests
- [ ] 6.4 Write Flask CORS pytest
- [ ] 6.5 Run ./gradlew test and ./gradlew assembleDebug

## Deviations from Design
- None for implemented scope. Repository uses `refreshFromBackend()` instead of full `suspend UiState<T>` contract; the full contract is deferred to PR 2 per user-scoped slice.

## Issues Found
- Flask API wraps ALL responses in `{"success": true, "data": ...}` envelope. Retrofit models use `ApiEnvelope<T>` wrapper to match this contract.
- No Gradle wrapper or OpenJDK present in the execution environment. Android tests were written but could not be executed. This must be resolved before verify phase.
