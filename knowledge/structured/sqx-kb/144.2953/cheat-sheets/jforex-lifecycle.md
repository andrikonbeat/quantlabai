# JForex strategy lifecycle cheat-sheet

Curated, original summary of public JForex 4 API knowledge (Dukascopy); NOT a
copy of the account-gated JForex User Manual (REQ-KDI-04).

## IStrategy lifecycle

A JForex strategy implements `com.dukascopy.api.IStrategy`:

| Callback | When | Typical use |
|----------|------|-------------|
| `onStart(IContext context)` | Strategy start | Subscribe instruments, init indicators, load state |
| `onBar(Instrument, Period, IBar askBar, IBar bidBar)` | Every closed bar | Bar-level logic: entries, exits, signal checks |
| `onTick(Instrument, ITick tick)` | Every tick | High-frequency logic, stop management |
| `onStop()` | Strategy stop | Cleanup: cancel orders, persist state |

Strategy instances are created by the platform; the engine calls the callbacks.
Order placement goes through `context.getEngine()`, prices through
`context.getHistory()` / `context.getIndicators()`.

## @Configurable parameters

Annotate user-editable fields with `@Configurable` so they appear in the
platform UI and can be tuned without recompiling:

```java
@Configurable("RSI period")
public int rsiPeriod = 14;
```

Rules: fields MUST be public, non-final, with a default value; primitive or
`String` types. This keeps SQX-generated JForex code tunable.

## ABL -> JForex translation rules

| ABL / SQX concept | JForex equivalent |
|-------------------|-------------------|
| Market open / bar event | `onBar` / `onTick` |
| Indicator calculation | `context.getIndicators()` (see block-to-snippet) |
| Order placement | `IEngine.submitOrder(...)` |
| Stop / target | `IOrder.setStopLossPrice` / `setTakeProfitPrice` |
| Strategy shutdown | `onStop()` cleanup |

Translate by intent: ABL blocks express *what* to compute; JForex expresses
*when* callbacks run. Do not map 1:1 mechanically — validate against the
version-pinned corpus first.

## Provenance

- Source: public JForex 4 API knowledge, curated by the project.
- License: project-authored summary; no licensed text reproduced.
- Version: SQX `144.2953` (JForex platform-agnostic).