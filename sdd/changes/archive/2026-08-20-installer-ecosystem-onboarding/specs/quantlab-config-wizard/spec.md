# Delta for quantlab-config-wizard

## MODIFIED Requirements

### Requirement: CONFIGURE-WIZARD — Collect settings

El sistema MUST presentar pasos TUI secuenciales para: carpeta de instalación de SQX (install_path), carpeta de instalación de JForex, modo de cuenta JForex (`demo|live`, default `demo`), host:port de JForex DAS, credenciales JForex y API keys (OpenAI, Anthropic, etc.). Cada paso MUST tener input de texto con validación al enviar. La password MUST enmascararse en la TUI, MUST escribirse solo en `~/.quantlab/config.yaml` (0600) y MUST NOT escribirse en state.json ni en logs.
(Previously: recolectaba solo el CLI path binario de SQX, host:port, credenciales y API keys; sin carpeta de instalación ni modo de cuenta)

#### Scenario: Wizard completo con install_path y account_mode

- GIVEN el usuario ingresa una carpeta SQX válida, carpeta JForex, account_mode=demo, credenciales y una API key válida
- WHEN el wizard llega a la pantalla de confirmación y el usuario confirma
- THEN `~/.quantlab/config.yaml` se escribe con 0600 incluyendo `sqx.install_path` y `jforex.account_mode=demo`
- AND `state.json config_hash` coincide con el SHA-256 del archivo

#### Scenario: Password nunca en estado

- GIVEN el usuario ingresa una password de JForex
- WHEN el wizard persiste la configuración
- THEN la password aparece solo en config.yaml (0600)
- AND no aparece en state.json ni en logs

### Requirement: VALIDATE-PATH — SQX path check

El sistema MUST verificar que la carpeta de instalación de SQX proporcionada existe y contiene el binario CLI (`sqcli`/`sqcli.exe`) en su raíz o en `bin/` (ValidateSQXPath). Ante fallo, MUST mostrar error y permanecer en el mismo paso.
(Previously: verificaba que un único path ejecutable existiera y fuera ejecutable)

#### Scenario: Carpeta SQX inválida

- GIVEN el usuario ingresa `/nonexistent` como install_path
- WHEN el usuario envía el campo
- THEN el sistema muestra un error y permanece en el paso
- AND no avanza hasta un path válido o cancelación

## ADDED Requirements

### Requirement: VALIDATE-MODE — Restricción de modo de cuenta (REQ-WIZ-1)

El sistema MUST restringir `jforex.account_mode` a `demo` o `live`, con default `demo` cuando el campo está vacío. Ante un valor inválido, MUST mostrar error y permanecer en el paso.

#### Scenario: Modo inválido rechazado

- GIVEN el usuario ingresa account_mode=paper
- WHEN envía el campo
- THEN el sistema muestra un error
- AND permanece en el paso hasta ingresar `demo|live` o cancelar