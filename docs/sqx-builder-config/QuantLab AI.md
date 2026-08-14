Importante analizar el alcance de los Customs Projects de SQX para realizar todo el flujo que se describe a continuación. Puede ser que haya parte de la arquitectura y el código que se puedan simplificar gracias al funcionamiento de SQX.

Importante el sistema de memoria: hay que diseñar un sistema de memoria persistente para poder reutilizar toda la información recopilada en las diferentes campañas, todo tipo de información relevante debe ser guardada y clasificada de forma concreta y accesible en cada momento para el usuario y para los agentes LLM toda esta capa de memoria debe funcionar como un aprendizaje continuo que va a mejorar el funcionamiento del sistema QuantLab con cada campaña e iteración del usuario, debe ser capaz de autocorregirse y aprender para no cometer errores la cuestión es: como los agentes LLM usan está información en el momento correcto y preciso?, como la tienen en cuenta cuando hace falta sin perder ningún dato?, todo esto y más factores relacionados debe abarcar el sistema que vamos a crear, tiene que estar preparado y soportar poder entrenar modelos LLM con esta información y conocimiento. Es imprescindible usar todo esto de manera privada y en algún momento a futuro poder usar informacion almacenada por otros usuarios para nutrir nuestros propios sistemas y modelos. Cabe destacar que QuantLab utiliza engram de la misma forma que lo usa gentle-ai también para persistir entre sesiones esto tiene alcance y no debe ser reemplazado si no complementado de manera eficiente porque aunque engram es bueno estoy seguro que no cubre por completo todo lo que necesitamos. Hay que explorar si se le puede dar uso a context7 y codegraph de alguna manera que son herramientas que gentle-ai explota y pueden servir.
Hay que definir: Como, Cuando, Donde, Porque y Para que se guarda la información.

Flujo del sistema QuantLab:
El usuario abre una carpeta dedicada a QuantLab y sus campañas supongamos que es primera vez, crea una carpeta nueva llamada: "Campañas QuantLab" y dentro de esa carpeta abre OpenCode y selecciona el agente QuantLab-Orchestrator. En esta carpeta es donde de forma siempre ordenada de una forma concreta específica enfocada en trading se van a guardar todos los artefactos que genera el sistema, no se puede generar un artefacto fuera de su orden respectivo.
OpenCode (QuantLab-Orquestrator)
El orquestador es la capa que contiene todo el sistema de harneses e infraestructura para dirigir el flujo de QuantLab, tanto el Orquestador como los sub-agentes y toda la infraestructura que sostiene el sistema de QuantLab están inspiradas y utilizan como referencia toda la tecnología, ideología y funcionamiento del repositorio gentle-ai pero adaptado a trading algoritmico cuantitativo, toma los conceptos sobre el que está construido gentle-ai como base sólida para levantar los cimientos de QuantLab así como todas las herramientas como engram y demás que instala gentle-ai como si fueran propias de QuantLab, de hecho QuantLab debe recomendar instalar gente-ai en el ecosistema de OpenCode porque ambos conviven exitosamente y se complementan aunque son herramientas diferentes.
Input del usuario: 
- Quiero crear una campaña con 100 USD.
↓
El orquestador define como se va a correr la campaña mediante un razonamiento profundo del input del usuario.
Ejemplo hipotético del flujo de razonamiento de un modelo LLM bajo la infraestructura y capa de harneses de QuantLab:
- Campaña de 100 USD
**Objetivo:** Un portafolio de trading algorítmico formado por estrategias automatizadas generadas en el software Strategy Quant X
**Builder, Backtest, Tester, Optimizer:** StrategyQuantX
**Broker:** Dukascopy (Tiene como ventajas, integración directa de datos históricos y código de salida en formato compatible con las estrategias generadas en StrategyQuantX y un servidor en la nube para alojar las estrategias mitigando la necesidad de un a VPS de terceros)
**Plataforma de trading:** JForex 4
**Gestión de dinero mínima de JForex 4:** 0.01 lote fijo
**CAPITAL**
**Capital inicial:** 100 USD; Aunque es un capital bajo, no cuento con más dinero para invertir, hay que minimizar riesgos, sobrevivir e intentar avanzar, no pretender ser millonario, solo tener un ingreso extra sin que la cuenta muera en el proceso.
**Limitaciones de capital:**
- Timeframes bajos (M5, M15, M30):
	Aspectos negativos:
	- Mercado más inestable
	- Datos históricos de menor calidad, con más gaps que pueden afectar de manera directa a la generación de estrategias.
	- Los costos transaccionales (spreads y comisiones) son un lastre operativo.
	Aspectos positivos
	- Stop Loos técnico de aproximadamente de 15 a 40 pips que representa un riesgo del 1.5 a 4% de la cuenta, aunque sigue siendo elevado es mas razonable para un capital bajo
- Timeframes altos (H1, H4)
	Aspectos negativos:
	- Stop Loos técnico de aproximadamente de 40 pips en adelante, que en una cuenta de 100 USD representa un alto riesgo de pérdida por tarde.
	Aspectos positivos:
	- Mercado más estable
	- Datos históricos de mayor calidad
	- Los costos transaccionales (spreads y comisiones) son más favorables.
Restricciones de Capital y Operativa
Unidad de Operación: 1,000 unidades (0.01 lotes estándar).
Gestión de Riesgo: Rango flexible del 1.5% al 2.5% por operación ($1.50 - $2.50 USD). Este riezgo representan pérdidas del entre 15 y 20 pips que es razonable en timeframes de M15.
Costos ECN: Comisión de $0.008 USD (round turn). 7 USD por lote estándar.
El portfolio opera íntegramente en M15 para permitir Stop Losses (SL) técnicos significativos. M15 es el límite técnico: Es la temporalidad donde un Stop-Loss de 15-25 pips es técnicamente sólido y encaja con tu riesgo de $1.50 - $2.50. Es ideal gestionar un riesgo menor máximo 1% pero no es posible por contradicciones entre timeframes demasiado bajo: más ruido, y más desventajas pero con mayor posibilidad de gestión de un riesgo más controlado y timeframes altos con más ventajas pero con SL técnicos más amplios que se traducen en riesgos más elevados para una cuenta pequeña.
Apalancamiento: El apalancamiento influye en la cantidad de capital que te congela la plataforma al abrir las operaciones. Normal: 1:50 Fin de semana: 1:30
Nota: Los SL y TP en pips fijos son más para referenciar los SL y TP técnicos promedios de el timeframe, en la práctica lo más viable es usar el ATR con el propósito de colocar los SL y TP.
**MERCADO**
**Mercado seleccionado**: Forex; aunque es un mercado más riesgoso que otros como, Futuros o Materias primas, te permite invertir con capital bajo y utilizar apalancamientos, que bien gestionado te abre las posibilidades a varias operaciones simultáneas.
Limitaciones del mercado:
- El volumen del mercado Forex no es de fiar ya que el mercado no es centralizado, cada broker impone sus limitantes en el volumen que se observan en los gráficos e indicadores. Por lo tanto hay que tener en cuenta esto a la hora de elegir los bloques de construcción en el builder de Strategy Quant X.
- Mercado no centralizado.
- Mercado menos seguro.
Descubrimientos durante pruebas en Strategy Quant X:
- Cuando se configura la precisión de datos a M1 o Data Tick no se genera ninguna estrategia ni pasan el test de robustez. Sin embargo la misma configuración pero con presicion (Selected timeframe only (fastest)). Si comienzan a aparecer.
INSTRUMENTOS A OPERAR
1. **Instrumento C:**
2. **Instrumento B:**
3. **Instrumento A:**
Los instrumentos variados son para tener más oportunidades, pero el portfolio no admite operaciones simultáneas solo una a la vez.
Para que tu portafolio en Dukascopy sea viable con 100 USD y lotes de 0.01, necesitamos instrumentos que combinen tres factores: spread mínimo, volatilidad contenida (para que los Stop Loss de <20 pips no salten por ruido) y baja correlación entre ellos.
Aquí tienes los 3 instrumentos seleccionados para tu ruta algorítmica:
## 1. EUR/USD (El Ancla del Portafolio)
* Justificación: Es el instrumento con el spread más bajo del mundo (promedio de 0.1 a 0.3 pips en Dukascopy). Para una cuenta de 100 USD, cada pip que ahorras en la entrada es dinero directo en tu bolsillo.
* Ventaja en SQX: Al ser el par más líquido, los datos históricos de Dukascopy son de máxima calidad, lo que reduce los "gaps" que mencionaste y hace que los tests en M1 Precision sean más fiables.
* Uso: Ideal para estrategias de Reversión a la Media en M15.
## 2. USD/CHF (Baja Volatilidad y "Safe Haven")
* Justificación: El franco suizo tiende a moverse en rangos más predecibles y con menos "latigazos" que el GBP o el AUD. Esto permite que un Stop Loss de 15-20 pips tenga una probabilidad de supervivencia mucho mayor que en otros pares.
* Ventaja en SQX: Es excelente para encontrar estrategias basadas en niveles de soporte y resistencia. Además, el valor del pip es muy similar al EUR/USD, lo que simplifica tu gestión de riesgo de "1 dólar por cada 10 pips".
* Uso: Estrategias de Breakout con filtros de sesión (operar solo en sesión Londres/NY).
## 3. AUD/USD (Volatilidad Moderada y Buen Equilibrio Operativo)
Justificación: El AUD/USD ofrece un equilibrio muy sólido entre volatilidad, spread bajo y movimientos relativamente limpios en M15. A diferencia de pares más agresivos como GBP/USD, suele presentar menos ruido y movimientos más estructurados, permitiendo que Stop Loss técnicos de 15-22 pips tengan mayor estabilidad en una cuenta pequeña de 100 USD.
**Ventaja en SQX:** Sus datos históricos suelen ser consistentes y con buena calidad en StrategyQuant X, facilitando la creación de estrategias más robustas y menos sensibles al ruido extremo. Además, su volatilidad moderada ayuda a encontrar sistemas con mejor equilibrio entre frecuencia operativa y estabilidad.
**Uso:** Ideal para estrategias de Reversión a la Media, Pullbacks y Breakouts moderados en M15, especialmente utilizando filtros de volatilidad y ATR dinámico para SL y TP.

------------------------------
## Tu Matriz de Riesgo con 0.01 lotes / 0.1 contratos:

| Instrumento | Riesgo por 20 pips | Volatilidad (ATR H1) | Recomendación SL |
| ----------- | ------------------ | -------------------- | ---------------- |
| EUR/USD     | $2.00              | Baja-Media           | 12 - 18 pips     |
| USD/CHF     | $2.10 (aprox)      | Baja                 | 15 - 20 pips     |
| AUD/USD     | $2.00              | Media                | 15 - 22 pips     |
↓
Sub-agente Research:
Es el encargado de hacer toda la búsqueda de información previa a la formulación de una hipótesis válida (Devuelve la información al orquestador)
- Quiero saber cómo el sub-agente realiza esta búsqueda, en que fuentes, que sistema utiliza para extraer datos útiles y confiables.
- Tengo entendido que el sub-agente es capaz de hacer análisis técnico y fundamental entre otras cosas, cuantos tipos de análisis hace?, cuantos tipos de datos extrae?, para que?, como lo hace?, con que datos y de que forma?, Lo está haciendo de la forma más adecuada?, hay una ruta mejor?, se puede reutilizar datos e infraestructura ya existente en el proyecto?.
↓
Con la información recopilada el orquestador que lleva el flujo de la campaña fórmula las hipótesis correspondientes (Tengo dudas si la formulación de las hipótesis es mejor hacerla en el mismo orquestador sin delegar un sub-agente o delegando, resuelve esta duda usando la forma más eficiente de hacerlo). Actualmente el Orquestador fórmula para utilizar de manera eficiente el contexto de la campaña hasta el momento.
- La formulación de la hipótesis debe cubrir, todos los aspectos fundamentales de una estrategia rentable, gestión de riesgo, gestión de capital, reglas objetivas, tener en cuenta comisiones, spreads, slippages, swaps, rollovers, horarios, régimen de mercados, tendencias, rangos entre otros conceptos importantes.
↓
Sub-agente SQX builder config:
Se encarga de parametrizar las hipótesis y configurar el builder de SQX. Dependiendo de la cantidad de hipótesis que se estén trabajando se configuran agrupándose por similitud o independientemente cada hipótesis en builders diferentes respectivamente dentro del Custom Project.
↓
Sub-agente Reviewer: 
Válida las hipótesis y las configuraciones hechas en el builder, si hay problemas reconfigura el builder para corregir o relanza el Research en caso de detectar problemas más profundos (ej: de lógica en las hipótesis). Cuando el Reviewer pasa en verde todo, devuelve una tabla resumen estructurada con más información siguiente:
- Pestaña o sección del builder que se está configurando (ej: What to build)
- Parámetro a configurar (ej: ) resumen breve de que hace y como funciona este parámetro dentro de SQX, en trading algoritmico cuantitativo y en la hipótesis, edge, ventaja estadística en la que se está aplicando. Todo esto con el objetivo de refrescar conocimientos, entender a la perfección el funcionamiento de SQX y el trading algoritmico cuantitativo en general para ayudar a tomar mejores desiciones.
- Configuración hecha (¿Como voy a configurar el parámetro?)
- ¿Porque lo voy a configurar así?
- ¿Para que lo voy a configurar así?
Todo esto se va a hacer parámetro por parámetro de cada pestaña de SQX incluyendo los parámetros elegidos en la pestaña ranking que hay unos cuantos parámetros como (Winrate, Drowdown, Expentacy) y de tantos parámetros que hay el usuario no saben que hacen la mayoría, ni porque se elijen unos y otros no, porque no se utilizan todos al mismo tiempo, cuáles son los importantes, entre otras cosas más que no considera un usuario normal y nuestro sistema tiene que manejarlo de forma efectiva y eficiente, enseñando al usuario a la vez que hace el trabajo, porque lo cierto es que SQX tiene muchos parámetros configurables y ahí es donde se pierde la mayoría, de tantad cosas que hay no se sabe que escoger, porque es mejor para cada hipótesis y edge estadístico.
↓
Luego del proceso de configuración cuando todo está correcto, viene la ejecución (generación de estrategias) y el monitoreo.
Todavía no tengo bien definido como va a ser todo el proceso de ejecución y monitoreo hay que plantearlo correctamente, no entiendo cómo OpenCode y el modelo LLM van a mantener el proceso activo y realizar un monitoreo del estado de la generación en SQX.
Básicamente esta es la capa que se encarga de notificar y recomendar al usuario de cómo avanza el proceso de generación de estrategias, brinda información útil que permite decidir si mantener el proceso de generación o cancelar para reconfigurar el builder, siempre con recomendaciones, durante todo este proceso el LLM puede revisar todos los datos disponibles para encontrar cuál bloqueante del proceso de generación de estrategias, ya sea a nivel de lógica de hipótesis o a nivel técnico con estas conclusiones puede brindar recomendaciones y apoyo, le puede indicar al usuario donde debe fijarse en el proceso donde se está rompiendo, o porque hay una demora excesiva, todo con evidencias comprobadas, el modelo debe entender que el builder puede tardar bastante tiempo en encontrar estrategias que puedan ser útiles.
- Si la generación tiene éxito pasa a la fase de revisión de los datos resultantes.
- Si hay problemas, dependiendo de la gravedad del asunto se crea un plan de acción utilizando los datos validados con evidencias para ver: qué estuvo fallando?, que es necesario reconfigurar?, hay problemas lógicos?, hay problemas técnicos?, encontrar porque está fallando la generación y desde que punto del flujo hay que retomar, puede ser una simple reconfiguración del builder o directamente comenzar a buscar nuevos edges estadísticos, hipótesis e ideas para restablecer el flujo desde el inicio.
↓
Todo esto es un loop que se repite y se valida con confirmación humana las veces que sea necesario hasta obtener un resultado:
El resultado esperado es un databank de estrategias generadas a partir de las hipótesis planteadas listas para comenzar el proceso de validación. Con un reporte y la web con los resultados sintetizados y esquematizados de forma fiel al resultado de SQX.
↓
Con toda la información lista y organizada se crea el plan de pruebas y validación de las estrategias.
↓
Sub-agente SQX retest config:
Funciona idéntico al sub-agente SQX builder config pero enfocado en las pruebas de robustez, cabe destacar que hay varias pruebas de robustez, casa una con variedad extensa de parámetros a configurar que tienden a confundir al usuario en necesito un análisis exhaustivo de cada prueba de robustez que existe dentro del bloque retester en el Custom Project.
↓
Sub-agente Reviewer:
Funciona idéntico al sub-agente Reviewer anterior pero enfocado en las pruebas de robustez
↓
Ejecución/monitoreo:
Enfocado en test de robustez.
↓
Análisis de resultados de los test de robustez
- Review de overffiting
- Recomendaciones de próximas desiciones según los resultados.
↓
El resultado esperado es un databank curado y validado correctamente, estrategias estadística y matemáticamente rentables.
↓
Sub-agente SQX Optimizer config:
Funcionamiento similar a los anteriores pero enfocada en el bloque Optimizer de el Custom Project
↓
Sub-agente Reviewer:
Funciona idéntico al sub-agente Reviewer anterior pero enfocado en la optimización de estrategias
↓
Ejecución/monitoreo:
Enfocado en la optimización de estrategias.
↓
Análisis de resultados de la optimización 
- Review de overffiting
- Recomendaciones de próximas desiciones según los resultados.
↓
El resultado esperado es un databank optimizado correctamente, sin riesgos de overffiting.
↓
Sub-agente SQX Portfolio Composser:
Se encarga de confirmar portafolios con las estrategias generadas y optimizadas, medir y optimizar sus resultados juntas. Esto es importante porque permite posteriormente decidir que estrategias servirán de remplazo a las que ya están conectadas, ninguna estrategia de conecta sin antes comprobar cómo funcionan todas juntas. Esto funciona porque las estrategias que están en real primero pasaron por aquí por ende se puede medir su comportamiento y correlación con las nuevas.
↓
Sub-agente Compiler:
Se encarga de exportar el bot al formato de código compatible del sistema al que se va a conectar en este caso es código java, importarlo dentro de la plataforma y probar si compila, en caso de éxito pasa, en caso de error se corrige el error que hace que falle la compilación de diagnóstica que cambia en la estrategia al corregir este error y se notifica al usuario la corrección hecha de forma que entienda que se hizo para que la estrategia compilara y funcionará correctamente.
↓
Sub-agente Despliegue Demo:
Se encarga de lanzar las estrategias en la cuenta demo de Jforex 4 para realizar un backtest dentro de la plataforma y comparar los resultados obtenidos con los de SQX ver si discrepan y tomar desiciones o si son similares y pasa, luego se dejan las estrategias conectadas durante un tiempo para ver su comportamiento en el mercado real enfrentándose a comisiones reales, spreads, slippages, swaps, rollovers, horarios y demás factores influyentes, todo en live pero con dinero demo. Resumen de los resultados de los backtest y la comparación. El problema que veo en esta fase es que Jforex 4 da.una cuenta demo de solo 14 días hábiles luego hay que entrar a crear una nueva.
↓
Sub-agente Archivado:
En esta etapa se crea o actualiza el plan de mantenimiento, despliegue, remplazo de estrategias antes de la degradación, toda esta capa es para dejar preparado el terreno para cuando ocurra algún problema con las estrategias que están en real, degradación de las estrategias y otra cosa ya tener un plan de acción para llevar a cabo los remplazos, todo documentado, verificado, con evidencias para que en ese momento solo sea revisión del usuario y aceptar o declinar el cambio el objetivo es que el sistema de mantenga siempre con un haz bajo la manga y pueda nutrirse constantemente de las estrategias frescas que se van generando. Aquí se lleva el control y conteo de todas las estadísticas de la cuenta real, estrategias desconectadas con motivo de desconexión, conectadas.con motivos de conexión, perdidas, ganancias, costos, retiros, comisiones, remplazo de estrategias. 


Guardián de la cuenta:
Guardián-Orquestrator
El orquestador que maneja todo el flujo dedicado al constate monitoreo de la cuenta real, detecta todo tipo de cambios y notifica al usuario, detecta la degradación de estrategias y lleva todos los datos de la cuenta real enviando resúmenes al usuario, es el encargado de proteger la cuenta de Drowdowns excesivos fuera de los cálculos previstos para el portfolio o estrategias concretas, lleva las métricas de las estrategias comparándolas con los resultados del backtest para ver en qué momento comienzan a desfazarse drásticamente los resultados, puede detectar regímenes de mercado, tendencias, rangos, monitorea el comportamiento de las estrategias durante los diferentes estados del mercado, comprueba constantemente las comisiones los slippages, swaps, spreads, horarios, toda la información obtenida en este flujo retroalimenta el flujo de QuantLab-Orquestrstor y viceversa. Se separan en dos flujos diferentes porque uno va enfocado directamente a toda la parte de la generación de estrategias y otro al despliegue y monitoreo de las estrategias en real aunque ambos conviven bajo el mismo ecosistema.