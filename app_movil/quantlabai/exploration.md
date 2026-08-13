# Exploration: Conectar app móvil QuantLab AI al backend real

## Current State

La app móvil es un **frontend de demostración puramente in-memory**:

- **QuantLabRepository** (`data/repository/QuantLabRepository.kt`) es un singleton con `StateFlow` hardcoded para: `systemHealth`, `campaigns`, `agents`, `strategies`, `approvals`, `activityEvents`, `chatMessages`, `autonomyPolicy`.
- **QuantLabViewModel** delega todas las operaciones al repositorio sin ninguna abstracción de red.
- **Navegación**: Single-Activity + Compose Navigation. 5 tabs principales (Dashboard, Campaigns, Chat, Agents, More) + 8 pantallas secundarias.
- **UI/Theme**: Paleta Graphite/ElectricCyan consistente, estética terminal oscuro. No se toca en la conexión al backend.
- **Dependencias de red presentes pero no usadas**: Retrofit, OkHttp, Moshi, Kotlin Coroutines ya están en `build.gradle.kts`. Room también está declarado pero sin DAOs implementados.
- **Sin persistencia local**, sin auth, sin networking, sin WebSocket, sin push.

## Affected Areas

| File/Ruta | Por qué está afectado |
|---|---|
| `data/repository/QuantLabRepository.kt` | Sustituir datos hardcodeados por llamadas a API + cache local |
| `data/model/Models.kt` | Posiblemente ajustar tipos para mapeo JSON real |
| `ui/QuantLabViewModel.kt` | Pasar de `repository.method()` a `repository.flowX()` / `repository.actionX()` con estados de loading/error |
| `ui/screens/DashboardScreen.kt` | Consume `systemHealth`, `campaigns`, `approvals`, `activityEvents` |
| `ui/screens/CampaignsScreen.kt` | Consume `campaigns` con filtros |
| `ui/screens/ChatScreen.kt` | Mock de respuestas AI — necesita endpoint real o streaming |
| `ui/screens/AgentsScreen.kt` | Consume `agents` |
| `ui/theme/Color.kt` | No cambia — se preserva la estética |
| `ui/QuantLabApp.kt` | Posiblemente agregar splash/auth guard |
| `build.gradle.kts` (app) | Agregar librerías: Retrofit/Moshi ya están, falta WebSocket y push |

## Real Backend Capabilities Available NOW

### Flask API (`sdk/quantlab/dashboard/app.py`)

| Endpoint | Método | Descripción | Estado |
|---|---|---|---|
| `/api/health` | GET | Status del servidor | ✅ Activo |
| `/api/campaigns` | GET | Lista de campañas desde KnowledgeStore | ✅ Activo |
| `/api/campaigns/<id>` | GET | Detalle + equity/trades/statistics | ✅ Activo |
| `/api/pipeline` | GET | Pipeline runs | ✅ Activo |
| `/api/pipeline/<id>` | GET | Detalle de pipeline run | ✅ Activo |
| `/api/stats` | GET | Agregados globales (Sharpe, DD, trades) | ✅ Activo |
| `/api/reports/generate` | POST | Generar reporte HTML/CSV/PDF | ✅ Activo |

### Python SDK disponible pero NO expuesto como API

| Componente | Estado API | Comentario |
|---|---|---|
| `CampaignOrchestrator` | ❌ No expuesto | Orquesta pipeline SQX end-to-end (validate→translate→run→poll→export→read→compute→store→report). Muy valioso pero requiere sqcli + SQX instalado. |
| `CommandDispatcher` | ❌ No expuesto | Controla SQX por HTTP CLI: start/stop/get_status/list_projects/export_results. Necesita daemon SQX corriendo. |
| `KnowledgeStore` | ✅ Usado por Flask | Lee del knowledge lake (JSON files). Base de datos de campañas. |
| `TimeSeriesStore` | ❌ No expuesto | SQLite local para métricas time-series del monitor autónomo. |
| `NotifierDispatcher` / `MobilePushNotifier` | ❌ No expuesto | Push notifications (fire-and-forget). No hay endpoint receptor. |
| `AutonomousMonitorDaemon` | ❌ No expuesto | Daemon asíncrono que monitorea equity live, detecta regime shifts, dispara alerts. |

### Limitaciones críticas del backend actual

1. **No hay auth**: No hay JWT, API keys, ni sesiones. Cualquier cliente puede llamar.
2. **No hay WebSocket**: Todo es polling HTTP.
3. **No hay endpoint de escritura**: Solo GETs + POST `/api/reports/generate`. No se puede crear campaña, aprobar estrategia, pausar agente, ni modificar autonomía.
4. **No hay push endpoint**: `MobilePushNotifier` existe pero el backend no escucha ni registra dispositivos.
5. **Gate decisions son filesystem IPC** (`/tmp/sqx-gates/`): No hay API para consultar/actuar sobre gates desde móvil.

## Gap Analysis: App wants vs Backend provides

### Lo que la app quiere mostrar (ya existe en UI)

| Feature móvil | Backend disponible | Gap |
|---|---|---|
| Dashboard health | `/api/health` | ✅ Conectable YA |
| Campaigns list | `/api/campaigns` | ✅ Conectable YA |
| Campaign detail + metrics | `/api/campaigns/<id>` | ✅ Conectable YA |
| Stats globales | `/api/stats` | ✅ Conectable YA |
| Pipeline list | `/api/pipeline` | ✅ Conectable YA |
| Pipeline detail | `/api/pipeline/<id>` | ✅ Conectable YA |
| Agents list | ❌ No hay endpoint | 🔴 Necesita backend |
| Agent detail + logs | ❌ No hay endpoint | 🔴 Necesita backend |
| Approvals queue (acciones) | ❌ No hay endpoint | 🔴 Necesita backend |
| Activity log | ❌ No hay endpoint | 🔴 Necesita backend |
| Chat con AI | ❌ No hay endpoint | 🔴 Necesita backend |
| New Campaign Wizard | ❌ No hay endpoint | 🔴 Necesita backend |
| Strategy Laboratory | ❌ No hay endpoint | 🔴 Necesita backend |
| Replacement Engine | ❌ No hay endpoint | 🔴 Necesita backend |
| Settings / Autonomy Policy | ❌ No hay endpoint | 🔴 Necesita backend |
| Infrastructure Health | `/api/health` (parcial) | 🟡 Parcialmente conectable |
| Push notifications | ❌ No hay endpoint | 🔴 Necesita backend + infra |

### Lo que necesita infraestructura nueva

| Necesidad | Prioridad | Dependencia |
|---|---|---|
| **Auth / API Key** | Alta | Necesaria para exponer escrituras |
| **WebSocket o SSE** | Media | Para real-time: agents, chat, activity log |
| **Push notification endpoint** | Media | FCM / APNS + registro de device token |
| **Endpoint de gates** | Media | Exponer `/tmp/sqx-gates/` como API |

## Proposed Architecture for Connected App

```
┌─────────────────────────────────────────────────────────┐
│                   Android App (Compose)                  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │   Screens    │  │  ViewModel   │  │   Repository   │  │
│  │ (UI pura)    │  │ (state holder)│  │ (abstracción)  │  │
│  └──────┬──────┘  └──────┬───────┘  └───────┬────────┘  │
│         │                │                   │           │
│         ▼                ▼                   ▼           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              Data Layer (Kotlin)                     │ │
│  │  ┌─────────────┐  ┌────────────┐  ┌──────────────┐  │ │
│  │  │  Retrofit   │  │   Room     │  │   WebSocket  │  │ │
│  │  │  API client │  │   cache    │  │   client     │  │ │
│  │  └─────────────┘  └────────────┘  └──────────────┘  │ │
│  └─────────────────────────┬───────────────────────────┘ │
└────────────────────────────┼────────────────────────────┘
                             │ HTTPS (REST + WS)
                             ▼
┌─────────────────────────────────────────────────────────┐
│              Flask Backend (Python)                      │
│  ┌──────────────┐  ┌────────────┐  ┌────────────────┐  │
│  │  REST API    │  │  WebSocket │  │   Push / FCM   │  │
│  │  (existing + │  │   (new)    │  │   (new)        │  │
│  │   new routes)│  │            │  │                │  │
│  └──────┬───────┘  └─────┬──────┘  └───────┬────────┘  │
│         │                │                  │           │
│         ▼                ▼                  ▼           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              QuantLab SDK (Python)                   │ │
│  │  KnowledgeStore │ CampaignOrchestrator │ CommandDisp │ │
│  │  TimeSeriesStore│ NotifierDispatcher   │ MonitorDaem │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Capas propuestas

1. **Data Layer (nuevo, Kotlin)**:
   - `ApiClient`: Retrofit con Moshi. Base URL configurable (default `http://10.0.2.2:8080` para emulador).
   - `CacheDatabase`: Room con entidades `Campaign`, `Agent`, `Strategy`, `Approval`, `ActivityEvent`, `ChatMessage`.
   - `RepositoryImpl`: Orquesta API → cache → StateFlow. Estrategia: `cache-first` para reads, `api-then-cache` para writes.
   - `WebSocketClient`: OkHttp WebSocket para real-time (agents, activity, chat).

2. **Backend — Nuevos endpoints (Python)**:
   - `POST /api/auth/token` — API key / device registration (simple, sin OAuth por ahora).
   - `POST /api/campaigns` — Crear campaña (delega a `CampaignOrchestrator` dry-run o real).
   - `POST /api/approvals/<id>/approve` — Aprobar/rechazar (actualiza KnowledgeStore o gate).
   - `POST /api/strategies/<id>/replace` — Replacement engine action.
   - `POST /api/agents/<id>/toggle` — Pausar/reanudar agente.
   - `POST /api/autonomy-policy` — Guardar política de autonomía.
   - `GET /api/agents` — Lista de agentes (desde knowledge lake o metadata).
   - `GET /api/activity` — Activity log global.
   - `WS /ws/updates` — Server-Sent Events o WebSocket para push de eventos.
   - `POST /api/push/register` — Registrar device token para FCM.

3. **Auth Strategy**:
   - Fase 1: API Key estática (configurable, sin usuario).
   - Fase 2: Device registration (cada dispositivo se registra y recibe un token).
   - Fase 3: JWT con PostgreSQL RBAC (schema existe en `docker/init-schema.sql` pero no implementado).

## Recommended Implementation Phases

### Phase 1: Read-Only Connection (1-2 semanas)

**Objetivo**: La app muestra datos REALES del backend sin modificar nada.

**Backend**:
- Nada nuevo — endpoints existentes son suficientes.
- Asegurar CORS si es necesario (Flask-CORS).

**App**:
- Crear `data/remote/ApiClient.kt` (Retrofit) con interfaces para `/api/health`, `/api/campaigns`, `/api/stats`, `/api/pipeline`.
- Crear `data/local/CacheDatabase.kt` (Room) con entidades base.
- Crear `data/repository/RemoteQuantLabRepository.kt` que reemplace `QuantLabRepository` para reads.
- Modificar `QuantLabViewModel` para exponer `UiState` sealed class (`Loading`, `Success`, `Error`).
- Conectar: Dashboard, Campaigns list, Campaign detail, Stats, Pipeline list.
- Mantener mocks para todo lo que no tiene endpoint.

**Entregable**: App funcional con datos reales de campañas, stats y pipeline.

### Phase 2: Local Cache + Offline Support (1 semana)

**Objetivo**: La app funciona sin conexión y cachea datos.

**App**:
- Implementar `CacheDatabase` completo (Room entities para todos los modelos).
- Strategy de cache: `cache-first` para reads, `api-then-cache` para writes.
- Sincronización periódica (WorkManager) o al recuperar conexión.
- Agregar `NetworkMonitor` para mostrar estado de conexión en UI.

**Backend**:
- Nada nuevo.

**Entregable**: App resiliente a desconexión.

### Phase 3: Write Capabilities + Auth (2-3 semanas)

**Objetivo**: La app puede modificar el estado del sistema.

**Backend**:
- Implementar endpoints de escritura: campaigns (POST), approvals (POST), agents toggle, autonomy policy.
- Implementar auth simple: API key header + device registration.
- Endpoint `/api/auth/register-device` para registrar FCM token.

**App**:
- Implementar `ApiClient` métodos POST/PATCH.
- Flujo de login/splash con API key.
- Conectar: New Campaign Wizard, Approvals (botones), Replacement Engine, Settings.
- Push notifications: Firebase Cloud Messaging (dependencias ya presentes).

**Entregable**: App full-duplex con auth y push.

### Phase 4: Real-Time (1-2 semanas)

**Objetivo**: Eventos en vivo sin polling.

**Backend**:
- WebSocket endpoint (`/ws/updates`) o SSE.
- Publicar eventos: activity log, agent status changes, campaign progress, approval requests.
- Integrar con `AutonomousMonitorDaemon` para streaming de métricas.

**App**:
- `WebSocketClient` con reconnect automático.
- Eventos real-time en: Chat (streaming AI), Activity Log (live feed), Agents (status updates), Dashboard (metrics push).
- Push notifications para eventos críticos (drawdown breach, approval pending).

**Entregable**: App con real-time y push.

## Risks and Dependencies

| Risk | Severity | Mitigation |
|---|---|---|
| **No hay auth en backend** | Alta | Implementar API key simple antes de exponer escrituras. No exponer Flask directamente a internet; usar reverse proxy. |
| **Flask no es production-ready** | Media | Usar gunicorn/uvicorn detrás de nginx. Para dev, Flask dev server es aceptable en LAN. |
| **SQX no disponible** | Media | El backend ya maneja `sqcli unavailable` gracefully. La app debe manejar `/api/health` mostrando degraded mode. |
| **KnowledgeStore es file-based** | Baja | Funciona para read-only. Para writes concurrentes, considerar lock o migrar a DB. |
| **No hay tests de integración** | Media | Agregar tests de contratos API (schema tests) antes de Phase 1. |
| **WebSocket no probado en backend** | Media | Usar SSE primero (más simple con Flask) antes de WebSocket full-duplex. |
| **Push notifications requieren FCM config** | Baja | Firebase BOM ya está en deps. Configurar proyecto en Firebase console. |
| **Room migration desde mock** | Baja | Migración gradual: RemoteRepo como opción, fallback a mock si API falla. |

## Key Files That Will Need Changes

### Nuevos archivos a crear

| Archivo | Responsabilidad |
|---|---|
| `app/src/main/java/com/example/data/remote/ApiClient.kt` | Retrofit interfaces + Moshi models |
| `app/src/main/java/com/example/data/remote/ApiService.kt` | Implementación Retrofit |
| `app/src/main/java/com/example/data/local/CacheDatabase.kt` | Room DB + DAOs |
| `app/src/main/java/com/example/data/local/Entities.kt` | Room entities |
| `app/src/main/java/com/example/data/repository/RemoteQuantLabRepository.kt` | Repositorio conectado |
| `app/src/main/java/com/example/data/model/UiState.kt` | Sealed class Loading/Success/Error |
| `app/src/main/java/com/example/data/websocket/WebSocketClient.kt` | OkHttp WebSocket |
| `app/src/main/java/com/example/util/NetworkMonitor.kt` | Connectivity observer |
| `app/src/main/java/com/example/util/DeviceTokenManager.kt` | FCM token registration |

### Archivos existentes a modificar

| Archivo | Cambio |
|---|---|
| `QuantLabRepository.kt` | Mantener como fallback mock; renombrar a `MockQuantLabRepository` |
| `QuantLabViewModel.kt` | Cambiar fuente de datos a nuevo repositorio; exponer UiState |
| `QuantLabApp.kt` | Posible splash/auth guard |
| `build.gradle.kts` | Agregar `androidx.credentials`, `com.google.firebase:firebase-messaging` si no están ya |
| `AndroidManifest.xml` | Agregar permisos de internet, notifications |

### Backend — Archivos a modificar/crear

| Archivo | Cambio |
|---|---|
| `sdk/quantlab/dashboard/app.py` | Agregar nuevos endpoints (auth, agents, activity, push register) |
| `sdk/quantlab/dashboard/` (nuevo) | `auth.py` — API key validation, device registration |
| `sdk/quantlab/dashboard/` (nuevo) | `websocket.py` — WebSocket server (Flask-SocketIO o Flask + websockets) |
| `sdk/quantlab/gates/` | Exponer gates como API endpoint |

## Ready for Proposal

**Sí, listo para propuesta.** La exploración muestra:

1. **Phase 1 es inmediatamente viable**: 5 endpoints del backend ya funcionan y cubren Dashboard, Campaigns, Stats y Pipeline.
2. **El gap principal es de escritura + real-time**: No hay endpoints para agents, approvals, chat, activity log, ni push.
3. **La arquitectura propuesta es incremental**: Empezar por read-only, agregar cache local, luego writes, luego real-time. No es necesario "hervir el océano".
4. **La estética Graphite/ElectricCyan se preserva intacta**: Todos los cambios son en la capa de datos, no en la UI.

**Lo que el orchestrator debe decirle al usuario**:
> Podemos arrancar YA conectando campañas, stats y pipeline al backend existente sin tocar la UI. Luego agregamos auth simple, endpoints de escritura, y finalmente real-time + push. La estética se mantiene igual; solo cambia la capa de datos.
