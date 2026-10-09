# Delta for installer-tools-install

## ADDED Requirements

### Requirement: Detección de herramientas (REQ-TOOLS-1)

El sistema MUST proveer `DetectOpenCode()` y `DetectGentleAI()` que localizan el binario vía LookPath y reportan la versión ejecutando el flag de versión del binario. La detección SHALL ser la única fuente para decidir "already installed ✓" en la pantalla de consentimiento. Un binario ausente o no ejecutable SHALL reportar "no instalado" sin error fatal.

#### Scenario: Herramienta instalada

- GIVEN `opencode` en PATH
- WHEN `DetectOpenCode()` corre
- THEN reporta instalado con versión
- AND la pantalla de consentimiento muestra "already installed ✓"

#### Scenario: Herramienta ausente

- GIVEN PATH sin `gentle-ai`
- WHEN `DetectGentleAI()` corre
- THEN reporta no instalado
- AND el flujo de onboarding continúa sin error

### Requirement: Instalación de OpenCode sin sudo (REQ-TOOLS-2)

`InstallOpenCode()` MUST ejecutar un preflight npm escribible: detectar gestores (nvm/fnm/volta) y verificar que el directorio global de npm es escribible por el usuario. Si es escribible, MUST ejecutar `npm install -g opencode-ai` sin sudo. Si se requiere elevación, MUST mostrar display-only el comando exacto y MUST NOT ejecutar sudo. Ante fallo de red o de instalación, MUST degradar a display-only y MUST NOT bloquear el onboarding.

#### Scenario: npm escribible → instala

- GIVEN el directorio npm global es escribible (p.ej. vía nvm)
- WHEN el usuario consiente instalar OpenCode
- THEN se ejecuta `npm install -g opencode-ai` sin sudo
- AND se reporta éxito o error de instalación

#### Scenario: npm requiere sudo → display-only

- GIVEN el directorio npm global no es escribible
- WHEN el usuario consiente
- THEN se muestra el comando exacto a copiar (con sudo)
- AND no se ejecuta ningún comando con sudo
- AND el onboarding continúa

#### Scenario: Fallo de red

- GIVEN npm no responde
- WHEN `InstallOpenCode()` intenta instalar
- THEN degrada a instrucciones display-only
- AND el flujo de onboarding no se interrumpe

### Requirement: Instalación de gentle-ai con checksum (REQ-TOOLS-3)

`InstallGentleAI()` MUST descargar el release binario GoReleaser (`gentle-ai_{version}_{os}_{arch}.tar.gz`) a `~/.local/bin`, MUST verificar el SHA-256 contra el checksum publicado antes de activar y MUST realizar el swap atómico (patrón update.go). Si no hay release para la plataforma o falla la red/checksum, MUST degradar a display-only del script oficial (`install.sh`/`install.ps1`). MUST NOT bloquear el onboarding ante fallo.

#### Scenario: Release disponible → binario instalado

- GIVEN existe release GoReleaser para la plataforma
- WHEN el usuario consiente instalar gentle-ai
- THEN se descarga el binario a `~/.local/bin`
- AND se verifica el checksum antes de activar
- AND el reemplazo es atómico

#### Scenario: Checksum inválido

- GIVEN el checksum descargado no coincide con el publicado
- WHEN `InstallGentleAI()` valida
- THEN no se activa el binario
- AND se degrada a display-only

#### Scenario: Plataforma sin release

- GIVEN no existe release para la plataforma (p.ej. Windows)
- WHEN el usuario consiente
- THEN se muestra el comando display-only (install.ps1)
- AND el onboarding continúa