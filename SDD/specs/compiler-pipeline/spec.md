# Compiler Pipeline Specification

## Purpose

Compiles exported JForex `.java` sources into `.jfx` packages using an external JDK (the bundled `j64/` is a JRE and MUST NOT be assumed to contain javac), with a bounded error-fix loop.

## Requirements

### Requirement: Compile and Package .jfx (REQ-29)

The system MUST compile exported `.java` sources with `javac` from a configured external JDK (Java 25-compatible) and package the compiled classes into a `.jfx` archive. Compilation MUST run per exported strategy.

#### Scenario: Export compiles and packages

- GIVEN a strategy exported to `/out/MyStrategy.java`
- WHEN `CompilerPipeline.compile("/out/MyStrategy.java")` runs
- THEN javac from the external JDK compiles the source
- AND a `.jfx` archive is produced next to the source
- AND compile errors return a structured error report

#### Scenario: Missing JDK fails closed

- GIVEN no external JDK configured
- WHEN compile is attempted
- THEN a CompilerConfigError is raised before javac runs
- AND no partial `.jfx` is produced

### Requirement: Error-Fix Loop (REQ-30)

The pipeline MUST route compile failures into a bounded fix loop: the error report feeds a fix attempt (LLM-guided), recompile, and re-validate up to `max_fix_iterations`; exceeding the bound MUST halt with a final error report. Each iteration MUST be logged.

#### Scenario: Fix loop self-corrects

- GIVEN a `.java` failing on a missing import
- WHEN the fix loop runs
- THEN a fix attempt amends the source and recompiles
- AND a `.jfx` is produced within the iteration bound

#### Scenario: Loop bound halts

- GIVEN a `.java` still failing after `max_fix_iterations`
- WHEN the loop exhausts its bound
- THEN the pipeline halts with a CompileError and full error history
- AND the failing source is not deployed
