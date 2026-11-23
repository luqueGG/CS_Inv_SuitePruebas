# Especificación preliminar del detector de Assertion Roulette (v0.1)

## Motivación
Assertion Roulette suele referirse a tests con múltiples aserciones cuya falla no permite identificar de forma inmediata qué comportamiento se verificó. La presencia de varias assertions **no es por sí sola prueba concluyente** del smell. Aquí se emplea una heurística estática, explícita y verificable para un piloto.

## Regla principal
1. Parsear con `ast.parse` los archivos Python de tests. Si hay `SyntaxError`, devolver estado `parse_error` con detalle y **no** reportar ausencia de olor.
2. Identificar funciones `def test_*` y `async def test_*` (incluidas dentro de clases `Test*`), sin ejecutar el módulo.
3. Contar los nodos `ast.Assert` que pertenecen al cuerpo de cada función, **excluyendo** los pertenecientes a definiciones anidadas para evitar atribución incorrecta.
4. Clasificar como `unlabeled` los `ast.Assert` con `msg is None`. No evaluar semánticamente si un mensaje existente es informativo.
5. Marcar test como `ar_candidate = true` si contiene **dos o más** `unlabeled` asserts. Emitir ruta, función, líneas, total de asserts, unlabeled y justificación breve.
6. Agregar métricas por archivo, función y run. Mantener fija esta versión del detector durante la comparación.

## Ejemplo
```python
def test_discount():
    assert discount(100, 10) == 90
    assert discount(50, 10) == 45  # candidato: 2 asserts sin msg

def test_tax():
    assert tax(100) == 18, "tax(100) debe ser 18"
    assert tax(0) == 0, "tax(0) debe ser 0"  # no candidato según esta heurística
```

## Feedback específico aceptable
- Señalar `test_discount` y líneas identificadas; explicar que una falla puede ser difícil de diagnosticar.
- Sugerir test cases separados y descriptivos, `pytest.mark.parametrize` con identificadores claros, o mensajes de fallo útiles, sin cambiar la semántica comprobada.
- No exigir mensajes en absolutamente todos los asserts ni reducir arbitrariamente cantidad de aserciones.

## Limitaciones conocidas (registrar en README)
- **Falsos positivos:** dos asserts simples y descriptivos pueden ser claros, aun sin mensaje.
- **Falsos negativos:** un solo assert opaco, mensajes genéricos, `pytest`-helpers, `unittest.assert*`, `pytest.raises`, comparadores custom, `pytest-check`, llamadas a helpers, parametrizaciones y aserciones implícitas pueden ocultar ambigüedad.
- El mensaje `assert ..., "texto"` puede ser inútil; esta versión no inspecciona su calidad.
- El detector no mide calidad global, independencia de tests, ni cobertura; tampoco sustituye una evaluación manual.
- Test functions parametrizadas pueden ejecutar varios casos, pero se cuentan una vez a nivel AST.

## Tests del detector
Cubrir: 0, 1 y 2 assertions sin msg; 2 assertions con msg; mezcla de msg/sin msg; varias funciones; métodos en `Test*`; función anidada; archivo con error sintáctico. Verificar líneas y que el detector no ejecute los tests.
