# SQX Task XML Dialect — Authoritative Evidence (Gap 1 / T3)

**Source**: StrategyQuant X 144/2953 Linux install (`/mnt/Projects/05 - Develop/Proyectos/1- Active/quantlab-ai/SQX_144_2953_linux_20260601/`)
**Collected by**: `gentle-ai-explore` task `mv6h4gxa-5-r5qz` + parent reads
**Date**: 2026-10-13

---

## Dialect Overview

Every task in a `.cfx` project renders as:
```xml
<Task type="..." name="..." title="..." active="true" taskXMLFile="...">
  <Settings>
    <TaskType>          <!-- e.g., <ClearDatabanks>, <CallExternalScript> -->
      ... children per type (see table below) ...
    </TaskType>
    <Databanks>
      <Databank name="Input" label="Input databank" value="..."/>
      <Databank name="Output" label="Output databank" value="..."/>
    </Databanks>
  </Settings>
  <Resources>...</Resources>
</Task>
```

**Key helpers** (from `internal/web/SQXBUSINESS/src/components/XMLUtil.js`):
- `addNode(name, value, parent, xmlDoc)` → creates/finds `<name>`, sets text content = `value`
- `getNodeValue(parent, name, default)` → reads text content of child `<name>`
- `getAttrStringValue(el, attr, default)` / `getAttrIntValue` / `getAttrBooleanValue` → reads attribute
- `setTaskInputDatabank(name)` / `setTaskOutputDatabank(name)` → writes `<Databank name="Input|Output" value="name"/>`

---

## Per-Type XML Shapes (Evidence Table)

| Type | XML Element & Shape | Children / Attributes | Evidence (path:line) |
|------|---------------------|------------------------|----------------------|
| **Build** | `<Build>` | `<Blocks>` + `<Options>` + `<RiskMoneyManagement>` | `TaskBuild/BuildTaskService.js:79-94`, `SettingsBlocks/BlocksService.js:270-350` |
| **Build** | `<Blocks><Calibration calibrateBeforeStart="bool" useMaxSteps="bool" maxSteps="int"/>` | attributes on Calibration | `BuildTaskService.js:83-85` |
| **Build** | `<Options><BuildTradingOptions><Params><Param key="..." className="...">value</Param></Params></BuildTradingOptions></Options>` | nested `<Param key className>` | `SettingsOptions/OptionsService.js:55-80` |
| **Build** | `<WhatToBuild><StrategyType type="..." additionalCharts="..." templateFile="..." .../></WhatToBuild>` | all attributes on StrategyType | `SettingsWhatToBuild/WhatToBuildService.js:90-100` |
| **Build** | `<RiskMoneyManagement><MoneyManagement><InitialCapital>num</InitialCapital><Method type="..." use="bool"><Params>...</Params></Method>...</MoneyManagement></RiskMoneyManagement>` | mixed | `SettingsMoneyManagement/MoneyManagementService.js:70-115` |
| **Retest** | `<CrossChecks>` with per-check structures (WFO, SPP, SequentialOpt, etc.) | see harvest | `SettingsCrossChecks/CrossCheckAcceptanceSettingsService.js:25-85` |
| **Optimize** | `<Optimization>` with Source, WalkForward, OptimizationMethod, WhatToParametrize, ManualSettings | mixed | `SettingsOptimization/OptimizationService.js:45-130` |
| **Filtering** | `<Filtering><ActionType>int</ActionType><MaxStrategies>int</MaxStrategies><Conditions>...</Conditions></Filtering>` | Condition children with Column-Value/Comparator/Numeric-Value | `SettingsFiltering/SettingsFilteringService.js:25-55` |
| **GoToTask** | `<GoToTask task="..." resetEvaluatedCycles="bool" resetActivatedCycles="bool"><Conditions>...</Conditions></GoToTask>` | attributes + Conditions | `SettingsGoToTask/SettingsGoToTaskService.js:20-45` |
| **AutomaticRetest** | `<CustomData><Setups><Setup dateFrom="..." ...><Chart .../><Commissions>...</Commissions><MainTestValues engine="true" symbol="true" .../></Setup></Setups></CustomData>` + Options/RiskMoneyManagement/Rankings/CrossChecks/Resources | attributes on Setup/Chart/Method/MainTestValues | `SettingsAutoRetestData/AutoRetestDataService.js:30-80, 180-240` |
| **AutomaticPortfolioBuilder** | `<AutomaticPortfolioBuilder><SearchType>...</SearchType><GenPopulationSize>...</GenPopulationSize>...<MoneyManagement><InitialCapital>...</InitialCapital><Method ...><Params>...</Params></Method></MoneyManagement></AutomaticPortfolioBuilder>` | child text for scalars, attributes for Method | `SettingsAutomaticPortfolioBuilder/AutomaticPortfolioBuilderService.js:25-95` |
| **CreatePortfolio** | `<CreatePortfolio><MaxStrategies>100</MaxStrategies></CreatePortfolio>` + databanks via DatabankService | child text MaxStrategies | `SettingsCreatePortfolio/SettingsCreatePortfolioService.js:8-10, :16-18` |
| **CustomAnalysis** | `<CustomAnalysis><PerStrategy1>...</PerStrategy1><PerStrategy2>...<FullDatabank1>...<FullDatabank2>...<Filter>bool</Filter><InputArgsPerStrategy1>...<InputArgsFullDatabank1>...</CustomAnalysis>` | all child text | `SettingsCustomAnalysis/SettingsCustomAnalysisService.js:35-55` |
| **LogDatabankStats** | `<LogDatabankStats><Databank>Results</Databank><LogStats type="sum"><Conditions>...<Column>...</Column></LogStats>...</LogDatabankStats>` | list of LogStats with `type` attr | `SettingsLogDatabankStats/LogDatabankStatsService.js:15-45` |
| **SaveToFiles** | `<SaveToFiles><DestDirectorySqx>...<DestDirectoryStr>...<SaveInSqxFormat>bool</SaveInSqxFormat>...<SaveSourceCode type="..." format="...">bool</SaveSourceCode>...</SaveToFiles>` | child text scalars, `SaveSourceCode` has attrs + text | `SettingsSaveToFiles/SettingsSaveToFilesService.js:25-65` |
| **LoadFromFiles** | `<LoadFromFiles><SourceDirectory>...<IncludeSubdirectories>bool</IncludeSubdirectories><UnrecognizedInstrumentAction>...<UnrecognizedInstrumentValue>...</LoadFromFiles>` | all child text | `SettingsLoadFromFiles/SettingsLoadFromFilesService.js:20-40` |
| **ApplyMassConfig** | `<ApplyMassConfig><LoadFrom><Type>...<File>...<Task>...</LoadFrom><WhatToApply><Data>bool</Data><TradingOptions>bool</TradingOptions>...<TargetTasks>comma,list</TargetTasks></ApplyMassConfig>` | child text, TargetTasks = comma-separated list | `SettingsApplyMassConfig/ApplyMassConfigService.js:45-110` |
| **CallExternalScript** | `<CallExternalScript><File params="...">path</File><WaitFor hours="0" minutes="0">end|time</WaitFor></CallExternalScript>` | File: text + `params` attr; WaitFor: text + `hours`/`minutes` attrs | `SettingsCallExternalScript/SettingsCallExternalScriptService.js:5-9, :15-21` |
| **ClearDatabanks** | `<ClearDatabanks><Databank name="X"/><Databank name="Y"/></ClearDatabanks>` | **LIST** of `<Databank name="..."/>` (attribute!) | `TaskClearDatabanks/TaskClearDatabanksService.js:34-40` |
| **DeleteFile** | `<DeleteFile><File>path</File></DeleteFile>` | child text | `SettingsDeleteFile/SettingsDeleteFileService.js:5, :11` |
| **Notification** | `<Notification><Type>email</Type><Email>...</Email><Wait>false</Wait></Notification>` | child text, defaults type=email wait=false | `SettingsNotification/SettingsNotificationService.js:10-13, :17-19` |
| **StopAndStart** | `<StopAndStart><StartProject use="true" skipToFirstProject="false">ProjectName</StartProject><Conditions/></StopAndStart>` | StartProject: attrs + text; Conditions child | `SettingsStopAndStart/SettingsStopAndStartService.js:48-54, :12-16` |
| **UpdateData** | `<UpdateData><Type>project</Type></UpdateData>` | child text, default project | `SettingsUpdateData/SettingsUpdateDataService.js:5, :11` |
| **WaitFor** | `<WaitFor><File>...</File><Action>user</Action></WaitFor>` | child text, default action=user | `SettingsWaitFor/SettingsWaitForService.js:5-6, :12-13` |
| **NeuralNetworkTrainer** | `<NeuralNetworkTrainer/>` (empty in task.xml; params in JAR) | **NO readable Settings* plugin** | `TaskNeuralNetworkTrainer/task.xml:3` |

---

## Contradictions with Prior Assumptions

| Prior Claim | Reality (from harvest) |
|-------------|------------------------|
| "7 types lack readable evidence" | **Only NeuralNetworkTrainer lacks a Settings* plugin**. The other 6 (CallExternalScript, DeleteFile, WaitFor, UpdateData, StopAndStart, ApplyMassConfig) have full JS serializers in `Settings*/Settings*Service.js`. |
| `render_generic` should "emit attributes" | The dialect is **per-type children** (text/attrs/lists), not a uniform attribute pattern. The `enabled="true"` attribute emitted by `render_generic` **does not exist** in the dialect. |
| CallExternalScript has `type` param | **No `type` param** in authoritative config (only file, params, waitfor, hours, minutes). `waitfor` is ENUM `end|time`, not boolean. |
| ClearDatabanks has single `databank` | **It's a LIST** of databanks rendered as repeated `<Databank name="..."/>` elements. |

---

## Notes for T3 Implementation

1. **ParamType.LIST** added to `params_schema.py` to model ClearDatabanks correctly.
2. Serializers must emit the exact child structure per type; a data-driven registry `TASK_XML_SERIALIZERS[TaskType]` is recommended.
3. The `Databanks` section is handled by `_databanks_section` in the renderer — already emits `<Databank name="Input|Output" value="..."/>`. Do not duplicate.
4. Task wrapper (`<Task type name title active taskXMLFile>`) is written by the CFX writer — ensure `taskXMLFile` matches the task type.
5. Build's complex sections (Blocks, Options, MoneyManagement) require dedicated serializers (T3-3).