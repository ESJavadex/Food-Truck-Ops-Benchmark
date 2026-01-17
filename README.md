# Food Truck Ops Benchmark

Benchmark ligero para evaluar capacidades de planificacion, optimizacion bajo restricciones y consistencia operativa en LLMs.

## Estructura
- Casos (privados): `data/food_truck_ops_cases.jsonl`
- Template de casos: `tools/case_template.json`
- Evaluador: `src/food_truck_ops/evaluator.py`
- CLI evaluacion: `tools/run_eval.py`
- CLI generacion OpenRouter: `tools/openrouter_generate.py`
- Leaderboard: `leaderboard/leaderboard.csv`

## Formato del caso (JSONL)
Cada linea es un caso con:
- `hours`: lista de horas (string) que deben cubrirse.
- `budget`: presupuesto maximo.
- `capacity_units`: capacidad de almacenaje.
- `locations`: demanda por hora y ubicacion.
- `menu_items`: items disponibles (precio fijo + ingredientes).
- `ingredients`: coste y almacenamiento por ingrediente.
- `constraints`: reglas adicionales.
- `profit_scale`: escala para convertir profit en score.

## Formato de salida esperado (predicciones)
Cada linea:
```json
{
  "id": "fto_001",
  "menu": [{"item": "Veg Wrap"}],
  "purchases": {"wrap": 40, "veggies": 80},
  "route": [
    {"location": "Office Park", "hours": ["09","10","11"]},
    {"location": "Station", "hours": ["12","13"]}
  ]
}
```

## Scoring
- Profit score (0-60): basado en `profit_scale`.
- Waste score (0-20): penaliza coste de ingredientes no usados.
- Constraint score (0-20): reglas cumplidas.

Si el plan no es valido (presupuesto, capacidad, horas incompletas, etc), el score es 0.

## Seguridad
- El dataset no se publica. Esta repo ignora `data/*.jsonl`.
- No commits de llaves API. Usa `OPENROUTER_API_KEY` en `.env` o entorno. Usa `.env.example` como plantilla.

## Ejecutar evaluacion
```bash
PYTHONPATH=src python tools/run_eval.py --preds predictions/openrouter_preds.jsonl --model my-model --update-leaderboard --tokens 12000 --cost 0.42 --runtime 18.4
```

Salida:
- Reporte: `leaderboard/report.json`
- Leaderboard actualizado: `leaderboard/leaderboard.csv`
- Reporte por modelo: `leaderboard/reports/<model>.json`

## Generar predicciones con OpenRouter
```bash
PYTHONPATH=src python tools/openrouter_generate.py --cases data/food_truck_ops_cases.jsonl --model openai/gpt-4o-mini --out predictions/openrouter_preds.jsonl
PYTHONPATH=src python tools/run_eval.py --preds predictions/openrouter_preds.jsonl --model openai/gpt-4o-mini --update-leaderboard --meta predictions/openai__gpt-4o-mini_meta.json
```

## Ejecutar varios modelos en paralelo
1) Crea `models.json`:
```json
{"models":["openai/gpt-4o-mini","openai/gpt-4.1-nano"]}
```
2) Ejecuta:
```bash
PYTHONPATH=src python tools/run_batch.py --models models.json --parallel 3
```

## UI de leaderboard
La interfaz vive en `web/index.html`. Abrela en el navegador y lee `leaderboard/leaderboard.csv`.
Si el archivo no existe, muestra estado vacio.

### Predictions Viewer (local)
Para mostrar predicciones en la UI, coloca el JSONL en `predictions/` con uno de estos nombres:
- `predictions/<model_safe>.jsonl` (ej: `openai__gpt-4o-mini.jsonl`)
- `predictions/<model>.jsonl` (ej: `gpt-4o-mini.jsonl`)

## Reglas soportadas (constraints)
- `required_location_hours`
- `max_price`
- `forbidden_item_hours`
- `vegan_only_hours`
- `max_menu_items`
- `min_menu_items`
- `must_include_item`
