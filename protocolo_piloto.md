# Protocolo mínimo del piloto (versión 0.1)

## Pregunta técnica
¿Puede un pipeline reproducible generar tests pytest con un LLM, revisarlos bajo dos estrategias controladas, detectar un indicador operacional de Assertion Roulette y calcular mutation score con mutmut? **No** se pretende contrastar hipótesis científicas en esta fase.

## Unidad y condiciones
- Unidad piloto: función Python determinista con especificación fija.
- Test inicial `v0`: **único por unidad**; se comparte entre ambas condiciones.
- Tratamiento `generic`: un turno de revisión que solicita mejorar las pruebas sin nombrar Assertion Roulette ni revelar la detección.
- Tratamiento `ar_specific`: un turno de revisión equivalente que recibe feedback concreto del detector e instrucciones orientadas a hacer las aserciones diagnosticables.
- Sin edición humana de salidas del LLM; permitir extracción mecánica simétrica y auditable.

## Variables principales (definiciones operacionales)
- `ar_flagged_tests`: cantidad de tests con al menos dos asserts sin mensaje en su propio cuerpo AST, según `criterios_detector.md`.
- `ar_unlabeled_asserts`: cantidad de `assert` sin mensaje en funciones `test_*`.
- `ar_total_asserts`: total de asserts encontrados en funciones `test_*`.
- `mutation_score`: porcentaje de mutantes matados sobre `killed + survived`, solo si baseline pytest pasa y hay denominador mayor que cero. Porcentaje o null; nunca imputar un valor en caso de fallo.
- Métricas secundarias: cantidad de tests, passed/failed/errors/skip, tiempo, tokens, errores de extracción y estados del mutador.

## Controles de comparabilidad
- Mismo archivo de producción, v0, modelo, parámetros, presupuesto de salida, número de revisiones, timeout, runtime, versión de dependencias, configuración de pytest y mutmut.
- El feedback específico agrega información diagnóstica **por diseño**; registrar longitud y tokens de prompts para transparentar la diferencia de contenido, no confundir igualdad de límite de tokens con prompts idénticos.
- No utilizar resultados de mutmut como feedback de revisión.
- Registrar cambios espontáneos en cantidad de tests/aserciones, ya que pueden alterar mutation score; **no** forzar artificialmente igualdad de tests generados.
- Preservar fallos, ambigüedades y casos sin mutantes aplicables, incluso si afectan la comparabilidad.

## Secuencia por unidad
1. Congelar código y especificación; calcular hash.
2. Generar una respuesta LLM v0; guardar prompt, respuesta y tests extraídos.
3. Detectar heurística AR en v0.
4. Solicitar revisión genérica de v0; guardar `v1_generic`.
5. Solicitar revisión específica de v0 con hallazgos; guardar `v1_ar_specific`.
6. Detectar AR en ambas v1, correr pytest y mutmut de forma idéntica; incluir v0 como referencia opcional/recomendada.
7. Exportar filas CSV y JSONL/manifest, incluyendo estado de intentos no completados.

## Condiciones de aceptación del demo
Como mínimo una función con ambas ramas completas, mismos `pair_id` y hash v0; idealmente todas las funciones piloto. README debe separar claramente salidas reales de fixtures sintéticos/replay. El ejemplo CSV debe indicar de dónde provienen sus números. No realizar inferencia estadística ni conclusiones causales.

## Decisiones pendientes para experimento definitivo
Selección y tamaño del dataset, replicaciones/semillas, orden aleatorio, definición validada del smell, estrategias de control de tamaño de suite, evaluación humana, política de mutantes equivalentes, análisis estadístico, potencia, proveedor/modelo definitivo y presupuesto. No resolverlas inventando supuestos ahora.
