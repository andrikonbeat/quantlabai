# Mobile Control Plane Specification

## Purpose

Define the read-only backend integration for the QuantLab AI mobile app. The system SHALL connect existing Compose screens to the live Flask backend through an API client, local cache, and repository facade while preserving Graphite/ElectricCyan UI.

## Requirements

### Requirement: API Client Layer

The system SHALL provide a Retrofit + Moshi client for existing Flask `/api/*` endpoints: `/api/health`, `/api/campaigns`, `/api/campaigns/{id}`, `/api/pipeline`, `/api/stats`. The client MUST use HTTPS in production and MUST NOT transmit authentication headers in Phase 1.

#### Scenario: Successful health fetch

- GIVEN the Flask backend is reachable at the configured base URL
- WHEN the API client calls `GET /api/health`
- THEN the client returns `200 OK` with parsed JSON body

#### Scenario: Network failure

- GIVEN the device has no network connectivity
- WHEN the API client attempts any endpoint call
- THEN the call throws a network exception within 10 seconds

### Requirement: Offline Cache Layer

The system SHALL provide a Room database caching campaigns, pipeline runs, stats, and health responses. Each cached entity MUST include a `fetchedAt` timestamp. The cache MUST survive process death.

#### Scenario: Cache persists after process kill

- GIVEN campaigns are cached with `fetchedAt`
- WHEN the app process is killed and relaunched
- THEN the repository returns cached campaigns with their original timestamp

### Requirement: Repository Facade

The system SHALL refactor `QuantLabRepository` into a facade over the API client and Room cache. The repository MUST expose suspend functions and MUST NOT expose raw Retrofit or DAO types to ViewModels.

#### Scenario: Repository returns cached data when offline

- GIVEN cached campaigns exist in Room
- AND the network is unreachable
- WHEN a ViewModel requests campaigns
- THEN the repository returns cached campaigns without throwing

### Requirement: ViewModel UiState

The system SHALL expose `UiState<T>` (Loading, Success(data), Error(message)) from all ViewModels that display backend data. The UI MUST render Loading, Success, and Error states.

#### Scenario: ViewModel emits loading then success

- GIVEN the network is reachable
- WHEN a ViewModel loads campaigns
- THEN it first emits `Loading`
- AND then emits `Success(campaigns)` on completion

### Requirement: Flask CORS Enablement

The system SHALL enable CORS on the Flask backend for the mobile dev origin. The backend MUST respond with `Access-Control-Allow-Origin` for the mobile app origin and MUST allow `GET` methods.

#### Scenario: Mobile origin receives CORS headers

- GIVEN the Flask app runs with CORS enabled
- WHEN a mobile-origin request hits `/api/health`
- THEN the response includes `Access-Control-Allow-Origin` matching the mobile origin

### Requirement: Offline-First Read Strategy

The system SHALL attempt a network read first; if the network read fails, it SHALL return cached data with timestamp. If no cache exists and the network fails, it SHALL return Error.

#### Scenario: Offline fallback with cache

- GIVEN cached stats exist with `fetchedAt = now - 5 minutes`
- AND the network is unreachable
- WHEN stats are requested
- THEN the system returns cached stats and exposes the timestamp to the UI

#### Scenario: Offline without cache

- GIVEN no cached health data exists
- AND the network is unreachable
- WHEN health is requested
- THEN the system returns `Error("No cached data available")`

### Requirement: Error Handling and Fallback

The system SHALL catch HTTP and network errors at the repository layer and translate them into `UiState.Error`. The system MUST NOT crash the UI on malformed responses.

#### Scenario: Malformed JSON fallback

- GIVEN the backend returns invalid JSON
- WHEN the API client parses the response
- THEN the repository catches the parsing exception
- AND returns `UiState.Error("Invalid server response")`

### Requirement: Phase 1 Auth Exclusion

The system MUST NOT include authentication, API keys, or tokens in Phase 1. All endpoints SHALL be accessed without credentials. Auth is deferred to Phase 3.

#### Scenario: Unauthenticated request succeeds

- GIVEN Phase 1 is active
- WHEN the app requests `/api/campaigns`
- THEN the request contains no Authorization header
- AND the backend returns `200 OK`
