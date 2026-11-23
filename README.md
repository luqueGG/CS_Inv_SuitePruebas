# Assertion Roulette Pilot (ar_pilot)

Prototipo experimental y reproducible que compara feedback genérico vs específico de Assertion Roulette para tests pytest generados por LLM, midiendo olor de prueba y mutation score con mutmut.

## Requisitos
- Python >= 3.11 (probado con 3.14)
- mutmut, pytest (dev)

## Instalación
```bash
python -m venv .venv
# activar entorno
pip install -e '.[dev]'
```

## Configuración LLM
Copiar `.env.example` a `.env` y completar `LLM_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`. Sin credenciales, usar `replay`.

## Comandos
```bash
python -m ar_pilot.cli list-functions
python -m ar_pilot.cli detect tests/test_detector.py
python -m ar_pilot.cli run --config configs/pilot.json --output artifacts/local_run
python -m ar_pilot.cli replay --fixture artifacts/demo/generations.jsonl --output artifacts/replay_run
python -m pytest -q
```

## Demo
`artifacts/demo/` contiene una ejecución **sintética** (no real de LLM) con una función y ambas ramas, logs de pytest/mutmut y CSV. Ver `manifest.json`.

## Detector
Heurística estática AST: test con >=2 asserts sin mensaje. Ver `criterios_detector.md`. Limitaciones documentadas allí.

## Métricas
- mutation_score = killed/(killed+survived)*100 solo si baseline pytest pasa y denominador>0; si no, null con motivo.
- Estados del mutador se conservan en `mutants_other` y logs.

## Riesgos
El código generado por LLM se ejecuta en subprocess; tratar como no confiable. Usar sandbox sin red si es posible.

## Limitaciones
- Piloto descriptivo, sin inferencia causal/estadística.
- Semilla no garantizada por proveedores.