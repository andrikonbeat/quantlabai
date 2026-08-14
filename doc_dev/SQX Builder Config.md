# **SQX Builder Config**

Resumen de todas las configuraciones que deben tener encuenta los agentes LLM para configurar SQX, con ejemplos de configuraciones hipotéticos, cabe la posibilidad que se me escape algo en caso de que notes me dices, el objetivo es cubrir todas las configuraciones del builder sin dejar ningún cabo suelto, debes comprobar que hace realmente cada configuración no solo confiar en lo que te voy a enviar debes verificado con evidencia en SQX.

Es imprescindible saber que con cada actualización de SQX pueden incluirse o descartarse nuevas funcionalidades y bloques de precisa diseñar un sistema que detecte versiones nuevas de SQX, revise el changelog oficial de SQX y pueda reajustar el sistema de QuantLab a esos nuevos cambios. Que no solo se guíe por la documentación si no que recorra las configuraciones realmente para ver los cambios y cuando tenga evidencia suficiente,. notificar al usuario, de lo que es necesario cambiar y actualizar en QuantLab para estar sincronizado.
### **What to build**
### **1\. Configuración de Salida y Tipo de Estrategia**
* **Strategy type:** Se ha seleccionado **Simple strategy \[default\]**, que genera una estrategia que opera en un solo símbolo y marco de tiempo.
### **2\. Configuración Adicional de Construcción (Additional build config)**
Esta sección define las reglas lógicas y el motor de generación:
* **Trading directions:** Se define según la necesidad del slot vacío (Long only, Short only o Bidireccional). En los ajustes específicos, se muestra **Both (Long & Short)** con las opciones de simetría (**Entry Symmetry** y **Exit Symmetry**).  
* **Strategy style:** Configurado en **SQX Signals Style**. No se utiliza lógica difusa (Fuzzy Logic) ni el estilo antiguo de SQ3.  
* **Build mode:** Establecido en **Genetic evolution**. Sus parámetros incluyen:  
  * Un máximo de 100 generaciones.  
  * 4 islas con 100 estrategias por isla.  
  * Uso de población inicial (**Initial population used**) y reinicio al terminar (**Restart on finish**).  
* **\# of Conditions, Periods:**  
  * **Conditions in entry rule:** Mínimo 1, Máximo 2\. 
  * **Conditions in exit rule (if enabled):** Mínimo 1, Máximo 2\.  
  * **Global Indicators period:** De 5 a 50\.  
  * **Global Lookback period (Shift):** Máximo 3\.  
  * **Number of Exit Types (SL/PT/etc...):** Máximo 3\.
### **3\. Configuración de Stop Loss**
El **Stop Loss** es obligatorio (**Required**) para garantizar la supervivencia del capital. Sus rangos son:
* **Fixed pips:** Entre 15 y 25 pips. (Desactivado) 
* **Percent based:** Del 1.5% al 2.5%. (Desactivado)
* **ATR-based:** Coeficiente (**ATR Multiple**) de 1.2 a 1.8, con un periodo (**ATR Period**) de 14 a 20\. 
* **Use indicator levels:** permitiendo niveles basados en indicadores como Bollinger Bands o EMA. (Desactivado)
### **4\. Configuración de Profit Target**
Al igual que el SL, el **Profit Target** es obligatorio (**Required**). Sus parámetros son:
* **Use same ranges as for Stop loss:** Desactivado, usar rangos diferentes para definir el riesgo.  
* **Fixed pips:** Entre 15 y 50 pips. (Desactivado)
* **Percent based:** Del 1.5% al 5%. (Desactivado)
* **ATR-based:** Coeficiente (**ATR Multiple**) de 1.2% a 2.2% con un periodo (**ATR Period**) de 14 a 20\.  
* **Use indicator levels:** (Desactivado)
* **Limit Risk-Reward (SL vs PT) ratio?:** Desactivado, lo que significa que no se ha forzado una relación fija entre el tamaño del SL y el PT en esta sección específica.
### **Genetic options**

### **1\. Genetic options (Opciones genéticas principales)**

* **Max \# of Generations:** **100**. Es el límite máximo de ciclos evolutivos que realizará el programa.  
* **Population Size (per island):** **100**. Define cuántas estrategias individuales conviven en cada isla.  
* **Crossover Probability:** **93%**. Es la probabilidad de que dos estrategias "padres" intercambien partes de su lógica para crear una nueva estrategia "hijo".  
* **Mutation Probability:** **30%**. La probabilidad de que ocurran cambios aleatorios en las reglas de una estrategia para introducir variabilidad.
### **2\. Islands options (Opciones de islas)**

* **Islands (separate evolution):** **4**. Se utilizan cuatro entornos de evolución independientes para fomentar la diversidad.  
* **Migrate every Xth generation, X \=:** **87**. Define que cada 87 generaciones, las mejores estrategias viajarán de una isla a otra.  
* **Population migration rate:** **6%**. Es el porcentaje de la población que se traslada entre islas durante la migración.

### **3\. Initial population generation (Generación de población inicial)**

* **Initial population size required:** **400**. Es el número total de estrategias necesarias para comenzar el proceso (100 por cada una de las 4 islas).  
* **Use strategies from Initial population databank as evolution start:** **Activado**. Permite que la evolución comience utilizando estrategias preexistentes si están disponibles en el banco de datos.  
* **Generated decimation coefficient:** **1**. Indica que no se generará un exceso de estrategias para filtrar antes de empezar la evolución.

### **4\. Filter generated initial population (Filtro de población inicial)**

* **Profit factor \> 1**: Solo se aceptan estrategias en la población inicial que tengan un factor de beneficio superior a 1 (que no sean perdedoras de entrada).
* Cabe destacar que aquí hay una lista extensa de condiciones que se pueden configurar cada una de forma diferente, la pega es que hay que elegir correctamente entre una lista extensa cuales se van a utilizar en cada caso con justificación y evidencias.

### **5\. "Fresh blood" (Sangre nueva)**

* **Detect same strategies in population and replace them with newly generated ones:** **Activado**. Evita la duplicidad de lógicas idénticas, manteniendo la diversidad genética.  
* **Replace % of weakest strategies with newly generated:** **10%**. Reemplaza el 10% de las estrategias con peor rendimiento por ejemplares totalmente nuevos.  
* **Every generation(s):** **2**. Este reemplazo de las más débiles ocurre cada dos generaciones.  
* **Show last generation databank \- for island \#1 only:** **Activado**. Permite visualizar los resultados de la última generación específicamente para la primera isla.

### **6\. Evolution management (Gestión de la evolución)**

* **Start again when finished (continuous repeating evolution):** **Activado**. Al terminar las 100 generaciones, el proceso vuelve a empezar automáticamente para seguir buscando mejores opciones.  
* **Restart evolution if fitness of \[In sample (whole)\] stagnates for X generation(s):** **30**. Si el rendimiento (fitness) de la población no mejora durante 30 generaciones consecutivas, la evolución se reinicia para intentar salir de un estancamiento lógico.

### **Data**
### **1\. Trading engine**
* **Engine:** **JForex**. Se selecciona este motor ya que la plataforma final de ejecución es JForex 4 de Dukascopy.
### **2\. Backtest data settings**
Esta sección define el activo y el horizonte temporal del análisis:
* **Symbol:** **EURUSD\_M1\_dukas** (como ejemplo principal, aunque se alterna según el slot del portafolio entre EU#R/USD y los demás instrumentos.
* **Timeframe:** **M15**. Es la temporalidad base elegida para permitir Stop Loss técnicos sólidos en cuentas pequeñas.  
* **Start day:** **2003.05.05**. Define el inicio del histórico de datos.  
* **End day:** **2025.12.19**. Define el final del histórico de datos para las pruebas.

### **3\. Test parameters**
Configuraciones que simulan las condiciones reales del mercado y costos operativos:
* **Precision:** **Selected timeframe only (fastest)**. Utilizada para agilizar la generación inicial de estrategias. Cuando se cambia a 1 minute data tick simulation las velas de construyen mejor y las estrategias fallan porque las simulaciones son más realistas, por solo cambiar este parámetro de puede pasar de generar estrategias a no generar nada por simplemente como se construyen las velas esto es importante.
* **Commissions & swap:** Configurado como **$7 per full lot**. Los valores de swap específicos para EUR/USD son **long: \-0.707 points** y **short: 0.37 points**.  
* **Spread:** **1 pip**. Se utiliza un valor conservador para asegurar la viabilidad de la estrategia ante variaciones de liquidez.  
* **Slippage:** **0.5 pips**. Simula la diferencia de precio entre la orden y la ejecución real.  
* **Min. distance:** **0 pips**.
### **4\. Data range parts**
Define cómo se divide la historia de los datos para validar la estrategia y evitar el sobreajuste (*overfitting*):
* **In sample \- Validation (ISV1 a ISV10):** Se han configurado **10 partes de validación**, cada una representando aproximadamente el **3%** del total de los datos.  
* **Out of sample \- Test (OOS1):** Se reserva un **30%** final de los datos (desde 2019.03.02 hasta 2025.12.19) para realizar una "prueba a ciegas" que confirme si la estrategia sigue siendo rentable en datos que nunca "vio" durante su creación.
* Todavía no tengo claro como se debe configurar esta opción correctamente, porque si luego voy a hacer un retest OOS a ciegas entonces porque en la generación debo incluir una parte de la data en OOS ?, Debo crear las estrategias y dejar una parte de la data sin que el motor de generación lo vea para esa parte que no ve es la que se valida en el retester? O como funciona esto ?
### **Trading options**
### **1\. Trading options (Opciones de operación)**
Esta sección define el comportamiento horario y operativo de las estrategias:
* **Don't trade on weekends:** **off**.  
* **Friday Close Time:** **00:38**.  
* **Sunday Open Time:** **00:38**.  
* **Exit At End Of Day:** **off** (las estrategias pueden mantener posiciones de un día para otro durante la semana).  
* **End Of Day Exit Time:** **23:04**.  
* **Exit On Friday:** **on**.  
  * **Justificación:** Se activa para cerrar todas las posiciones el viernes a las **20:40**. Esto se debe a que una cuenta de $100 USD no tiene el margen suficiente para soportar un **Gap de fin de semana** en contra.  
* **Limit Time Range:** **off**.  
  * **Time Range From / To:** **08:00 / 16:00** (desactivado).  
* **Exit At End Of Range:** **off**.  
* **Order Types To Close:** **All** (se cierran todas las órdenes pendientes y abiertas al final del rango permitido).  
* **Max distance from market:** **off**.  
* **Max distance percent:** **6** (desactivado).  
* **Maximum Trades Per Day:** **0**.  
  * **Nota técnica:** Aunque en la configuración general aparece en 0 (sin límite), el protocolo de generación de reemplazos recomienda establecerlo en **1** para evitar el *overtrading* y comisiones excesivas en una cuenta pequeña.  
* **Minimum / Maximum SL:** **0 / 0** (no se imponen límites adicionales aquí, ya que se controlan en la pestaña *What to build*).  
* **Minimum / Maximum PT:** **0 / 0**.  
* **Realistic Gaps Handling:** **on** (asegura que el backtest considere los saltos de precio de manera realista para mayor robustez).
### **2\. Build options (Opciones de construcción)**
* **Store Chart Data:** **off** (desactivado para ahorrar espacio y mejorar el rendimiento del procesamiento).

# Building blocks
Los building blocks son super importantes estas son básicamente lo que le da la dirección que van a tomar las estrategias generadas, el agente LLM debe tener un conocimiento amplio del funcionamiento de cada bloque y su configuración interna para de esta manera poder decidir que quitar que poner en cada campaña para cada hipótesis o Edge que se quiera trabajar.

**1\. Signals (Predefined conditions)**
* **Selección:** **188 blocks selected**.  
* **Total:** 339 blocks
* **Descripción:** Son condiciones completas predefinidas que combinan indicadores con comparaciones o propiedades específicas.  
* **Ejemplos incluidos:**  
  * **ADX, ATR, Awesome Oscillator**.  
  * **Bollinger Bands, CCI, Directional Index, Ichimoku, MACD, RSI, Stochastic**.  
  * **Bar And Time:** Condiciones basadas en horas, minutos o días específicos de la semana.
#### **2\. Indicators**
* **Selección:** **69 blocks selected**.  
* Total: 106 blocks
* **Funcionamiento:** Estos bloques se combinan aleatoriamente con operadores para crear nuevas condiciones lógicas.  
* **Exclusiones críticas:** Se han **desactivado** específicamente `{Indicator Crosses Above MA, Indicator Crosses Below MA, Indicator Below MA, Indicator Above MA}` debido a que no tienen conversión compatible a código **Java JForex** dentro de SQX.  
* **Categorías incluidas:**  
  * **Indicators:** ADX, ATR, CCI, EMA, MACD, RSI, SMA, etc..  
  * **Prices:** Ask, Bid, Close, Open, High, Low, y precios diarios/semanales/mensuales.  
  * **Operators:** Símbolos de comparación como `<`, `>`, `=`, e indicadores de tendencia como `Is falling` o `Is rising`.
### **3\. Stop/Limit entry blocks**
* **Selección:** **41 blocks selected**.
* Total: 58 blocks
* **Uso:** Se utilizan para definir el precio de entrada cuando se abren órdenes de tipo **Stop** o **Limit**.  
* **Fórmula base:** `Price level +/- Multiplicator * Price Range`.  
* **Componentes:** Incluye niveles de precio (como **Bollinger Bands, Ichimoku, Moving Averages**) y rangos de precio (como **ATR, BarRange, Fixed pips**).
### **4\. Order types**
* **Selección:** **Todas seleccionadas**.  
* **Tipos incluidos:**  
  * **(MKT) Enter at market:** Entrada inmediata a precio de mercado.  
  * **(MKT) Enter/reverse at market:** Entrada y reversión de posición.  
  * **(STOP) Enter at stop:** Entrada mediante orden condicionada de stop.  
  * **(LMT) Enter at limit:** Entrada mediante orden limitada.
### **5\. Exit types**
* **Selección:** **Todas seleccionadas**, pero con prioridades específicas.  
* **Obligatorios (Required):** El **Profit Target** y el **Stop Loss** deben estar activados siempre para garantizar la supervivencia del capital.  
* **Otros tipos disponibles:** `Exit After Bars`, `Move SL 2 BE`, `Trailing Stop` y `ExitRule`.
### **6\. Configuración de Calibración**
* **Calibrate indicators:** Configurado en **On (calibrate before start)**. Esto permite ajustar los parámetros de los bloques antes de iniciar la generación para que se adapten mejor al mercado seleccionado.

### "La pestaña ATM claramente SQX indica que es experimental y no se como funciona"
### **Money management**
### **1\. Configuración del Capital Inicial**
* **Initial capital**: **100**.  
  * **Explicación:** Representa el **capital base de la cuenta ($100 USD)** sobre el cual se realizan todas las simulaciones y el cálculo de métricas de supervivencia.
### **2\. Método de Gestión de Dinero (Choose Money Management method)**
* **Fixed size**: **Seleccionado**.  
  * **Explicación:** La estrategia operará con un **número fijo de lotes** en cada transacción.  
  * **Justificación:** Se ha seleccionado este método en lugar de un porcentaje de riesgo (como *Risk fixed % balance*) debido a que en cuentas de nano-capital, el uso de porcentajes de riesgo en la generación **distorsiona los resultados finales**.
### **3\. Parámetros del Tamaño de Orden**
* **Order size**: **0.01**.  
  * **Explicación:** Define el volumen de operación como **0.01 lotes estándar** (equivalente a 1,000 unidades del activo).  
  * **Justificación:** Esta es la **unidad mínima de operación** permitida y es necesaria para que el riesgo por operación se mantenga dentro del rango flexible de $1.50 a $2.50 USD.

## **Cross checks (robustness)**
Aquí tengo muchas dudas no sé si utilizar un bloque de Retester exclusivamente para hacer las pruebas de robustez o en el mismo bloque builder con solo activar los cross checks y configurarlos bien obtengo el mismo resultado que con un bloque Retester exclusivo ? Hay que investigar ventajas y desventajas y que conviene mejor.
Estoy realmente preocupado por toda la amplia gama de configuración y combinaciones que se pueden hacer aquí y no manejo esto muy bien los modelos LLM deben estar capacitados para configurar todo esto perfectamente pudiendo hacerlo con evidencias concretas y siempre guiando y notificando al usuario.

### **1\. BASIC (FAST)**
Estas pruebas son rápidas porque requieren una cantidad mínima de simulaciones adicionales.
* **What If simulations:**
  * **Configuración:** 15 simulaciones con 3 condiciones de filtrado.  
  * **Explicación:** Evalúa escenarios alternativos, como operar solo en ciertos días o excluir las mejores/peores operaciones para ver si la rentabilidad depende de eventos aislados.  
  * **Filtros:** Debe cumplir un **Profit factor \> 1.3** y un **Ret/DD Ratio \> 4** tras las simulaciones.  
* **Monte Carlo trades manipulation:**
  * **Configuración:** 2 tests con 30 simulaciones y 2 condiciones.  
  * **Explicación:** Desordena la secuencia de las operaciones (**Resampling**) y omite aleatoriamente un 10% de los trades para verificar la estabilidad de la curva de equidad.  
  * **Filtros:** El beneficio neto debe mantenerse al menos en un **60% del original** con un nivel de confianza del 80%.  
* **Higher backtest precision:**

  * **Configuración:** Simulación basada en **1 minute data tick simulation** con 3 condiciones.  
  * **Explicación:** Ejecuta un backtest más lento y preciso con un spread mayor (3 pips) para confirmar que la estrategia funciona bajo condiciones de mercado más costosas.  
  * **Filtros:** El beneficio neto y el número de trades deben ser al menos el **80% del backtest original**.

---

### **2\. STANDARD (SLOW)**

Pruebas que multiplican el tiempo de procesamiento al requerir múltiples backtests completos.

* **Backtests on additional markets:**
  * **Configuración:** Retest en un símbolo similar (ej. **GBPUSD\_M1\_dukas**).  
  * **Explicación:** Verifica que la lógica capture un patrón de mercado general y no solo ruido específico de un par.  
  * **Parámetros:** Se aplica spread de 0.6 y comisión de $7 por lote.  

* **Monte Carlo retest methods:**
  * **Configuración:** 6 tests con 10 simulaciones y 2 condiciones.  
  * **Explicación:** La prueba más dura; varía aleatoriamente los datos históricos, el spread, el slippage y los parámetros de la estrategia simultáneamente.  
  * **Filtros:** El **Net Profit** debe ser al menos el 50% del original y el **Max DD %** no debe superar el 200% del original (confianza 80%). 

* **Sequential Optimization:**
  * **Configuración:** Distribución de valores Up/Down del 50% con 50 pasos.  
  * **Explicación:** Optimiza los parámetros de forma secuencial para encontrar rangos de estabilidad.  
  * **Filtros:** El **80% de los parámetros** deben pasar la prueba de estabilidad.

---

### **3\. EXTENSIVE (SLOWEST)**

Procesos exhaustivos que evalúan la estrategia en diferentes rangos de tiempo y configuraciones.

* **Opt. Profile / Sys. Param. Permutation:**
  * **Configuración:** Máximo de 1,000 optimizaciones con 4 condiciones.  
  * **Explicación:** Analiza el perfil de optimización para asegurar que los parámetros elegidos no sean "picos" aislados de ganancia, sino parte de una zona rentable amplia.  

* **Walk-Forward Optimization:**
  * **Configuración:** 10 ejecuciones (runs) con un 20% de datos **Out of sample**.  
  * **Explicación:** Simula cómo se habría comportado la estrategia si se hubiera optimizado y re-optimizado periódicamente en el pasado.  
  * **Filtros:** El **Robustness score** debe ser mayor o igual al 50%.  

* **Walk-Forward Matrix:**
  * **Configuración:** Rango de Out of sample del 10% al 40% con 5 a 20 ejecuciones.  
  * **Explicación:** Una matriz de múltiples pruebas Walk-Forward para encontrar la combinación ideal de periodos de optimización y prueba.  
  * **Filtros:** Requiere que al menos una zona de 2x2 en la matriz tenga un puntaje de robustez del 80%, con un **WF Net Profit (OOS) \> 0**.

Imagina que la pestaña **Cross Checks** es el **entrenamiento de un astronauta**: no basta con que sepa pilotar en el simulador (backtest inicial). Con estas pruebas, lo metes en la centrífuga (Monte Carlo), le cambias la gravedad (Additional Markets) y le saboteas los controles (What If) para asegurarte de que, cuando esté solo en el espacio (cuenta real de $100), sabrá sobrevivir a cualquier imprevisto.

## **Ranking**
## **1\. Maximum top strategies to store (Capacidad y Parada)**

* **Maximum strategies to store in databank:** **100**.
  * **Explicación:** Se configura para guardar únicamente las mejores estrategia que pase todos los filtros, optimizando el espacio para el slot específico que se busca llenar.  
* **Stop generation when:** **Databank is full (reached maximum capacity)**.  
  * **Explicación:** El proceso de generación se detiene automáticamente en cuanto se encuentra una estrategia que cumple con todos los requisitos de calidad y robustez.

### **2\. Strategy Quality ranking (fitness) (Métricas de Rendimiento)**

Esta sección define qué métricas prioriza el algoritmo genético para decidir qué estrategias son "superiores":

* **Use:** **Main data backtest**.  
* **Compute from:** **Weighted Fitness (multiple goals)**.  Aquí también hay una serie extensa de posibilidades de parámetros y combinaciones entre ellos esto también hay que estudiarlo bien y los agentes LLM deben saber que están haciendo 
* **Ranking Criterium (Metas y Ponderación):**  
  * **Ret/DD Ratio:** **Maximize (Weight: 40\)**. Es la métrica más importante, priorizando la relación entre retorno y riesgo.  
  * **Max DD %:** **Minimize (Weight: 25\)**. Busca reducir la caída máxima de la cuenta.  
  * **Profit factor:** **Maximize (Weight: 15\)**.  
  * **R Expectancy:** **Maximize (Weight: 10\)**.  
  * **Ambiguous Trades %:** **Minimize (Weight: 5\)**. Para asegurar que la estrategia sea ejecutable sin ambigüedades técnicas.  
  * **Complexity:** **Minimize (Weight: 5\)**. Penaliza las estrategias con demasiadas reglas para evitar el sobreajuste.

### **3\. Custom filters (Filtros de Calidad Técnica)**

Define los umbrales mínimos obligatorios que una estrategia debe superar para ser guardada:
Importantísimo también con una lista extensa de posibilidades y combinaciones entre parámetros.

* **Profit factor (IST) \> 1.2:** En la parte de validación inicial.  
* **Profit factor (OOS1) \> 1.1:** En la prueba "fuera de muestra" (Out of Sample).  
* **Profit factor (ISV) \> 1.01:** En los segmentos de validación cruzada.  
* **Ret/DD Ratio \> 3:** Asegura una recuperación sólida frente al riesgo.  
* **Avg. Trades Per Month \> 5:** Evita estrategias que operan muy poco y carecen de relevancia estadística.  
* **Expectancy \> 5:** Expectativa mínima de ganancia por operación.  
* **Max Consec. Losses \< 10:** Límite de rachas perdedoras para proteger la psicología y el capital.

### **4\. Automatic filters (Limpieza de Estrategias Inválidas)**

Se activan para descartar automáticamente estrategias con problemas operativos (Dismiss strategies with these problems):

* **No trades / Too little trades:** Descarta las que operan insuficientemente.  
* **Zero PL trades / Zero duration trades:** Elimina errores de lógica donde no hay ganancia/pérdida o tiempo en mercado.  
* **Too many ambiguous trades:** Filtra lógicas que el motor no puede procesar con precisión.  
* **Outlier trade:** Elimina estrategias cuyo beneficio depende de una única operación excepcionalmente grande.

### **5\. Fit to existing portfolio filter (Correlación)**

Asegura que la nueva estrategia sea un buen complemento para las que ya están operando:

* **Existing portfolio databank:** **Grove**.  
* **Filter out strategies with correlation \> 0.3:** Descarta cualquier candidata que se mueva de forma muy similar a las estrategias actuales.  
* **Correlation settings:**  
  * **Correlation by:** **Day** (o Hour según el ajuste específico).  
  * **Of:** **Profit/Loss**.

Puedes imaginar la pestaña **Ranking** como el **departamento de Recursos Humanos** de una empresa: el **Fitness** es el currículum del candidato (qué tan bueno es), los **Custom filters** son los requisitos mínimos (título, experiencia), y la **Correlation** es la prueba de equipo para asegurar que el nuevo empleado no haga exactamente lo mismo que el que ya está sentado al lado, permitiendo que la "oficina" (tu portafolio) sea realmente eficiente y diversa.

El bloque Optimizer hay que explicarlo.
Al igual que Portfolio máster y porfolio Composer que no se cómo funcionan ni que diferencias hay entre ellos.