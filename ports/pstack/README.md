# pstack para Codex y Antigravity

Adaptación personal de [pstack de Lauren Tan](https://github.com/cursor/plugins/tree/main/pstack).
Una base común, dos adaptadores y cambios originales conservados en `pstack/`.
La adaptación es funcional, no una reproducción idéntica de Cursor.

## Usar

Codex: `$pstack-poteto-mode reproduce este bug, corrige la causa y verifica el resultado`.
Antigravity: `/pstack-poteto-mode` seguido de la tarea. También se puede pedir la skill por nombre.
Para conocer las skills: `pstack-poteto-help`. No se activa un modo persistente ni un scheduler.

Los 52 nombres llevan `pstack-` para evitar colisiones. Los flujos son secuenciales por defecto.
Solo una solicitud humana explícita habilita el uso de subagentes; una capacidad ausente no se simula.
El modelo actual se conserva. No se agregan hooks, conectores, credenciales ni agentes registrados.

## Setup reproducible (Python 3, sin dependencias)

Desde la raíz del fork:

```sh
python3 -m unittest discover -s ports/pstack/tests -v
python3 ports/pstack/pstack.py build --host codex
python3 ports/pstack/pstack.py build --host antigravity
python3 ports/pstack/pstack.py install --surface codex
python3 ports/pstack/pstack.py install --surface antigravity
```

`install` solo muestra el plan. Añadir `--apply` instala con copia de seguridad y manifiesto
de propiedad. Las colisiones y modificaciones locales bloquean el reemplazo; las skills
ajenas nunca se sobrescriben. `--destination` permite instalar primero en un proyecto
de prueba. Para Windows, el bloqueo del instalador debe adaptarse: esta versión soporta macOS/Linux.

Superficies disponibles:

| Superficie | Destino global |
|---|---|
| codex | `~/.codex/skills` (setup local de este usuario/CLI) |
| antigravity | `~/.gemini/config/skills` (Antigravity 2.0) |
| antigravity-cli | `~/.gemini/antigravity-cli/skills` |
| antigravity-ide | `~/.gemini/antigravity/skills` |

Codex también documenta `~/.agents/skills`; se puede seleccionar mediante `--destination`.
No instalar la misma skill en ambas ubicaciones: podría aparecer duplicada.
Los destinos de Antigravity se eligen explícitamente porque cambian entre superficies.

## Revertir

El resultado de instalación devuelve `backup`. Para revisar y ejecutar la restauración:

```sh
python3 ports/pstack/pstack.py rollback /ruta/devuelta/en/backup
python3 ports/pstack/pstack.py rollback /ruta/devuelta/en/backup --apply
```

La restauración rechaza cambios locales posteriores para no destruirlos. Conserva backups.

## Actualizaciones

`main` contiene la adaptación; `upstream-clean` identifica la base original sin modificaciones.
No hay ramas permanentes por host. Las ramas de revisión son `chore/pstack-sync-<sha>`.

El workflow semanal y manual detecta cambios **solo de pstack**, crea una issue de preparación
y un PR **draft**, sin refrescar el lock, fusionar ni instalar. `status:approved` en esa issue
autoriza únicamente la preparación del PR bajo este setup, no aprueba los cambios originales.
Los checks fallan intencionalmente mientras los archivos no coincidan con el lock revisado.
Si GitHub impide crear PRs mediante su token, el job falla explícitamente; no se instala un PAT.

Después de revisar los cambios originales y adaptar recetas/principios:

```sh
python3 ports/pstack/pstack.py lock --commit SHA_COMPLETO --reviewed
python3 -m unittest discover -s ports/pstack/tests -v
```

Probar descubrimiento y comportamiento en ambos hosts antes de marcar el PR listo.
Actualizar `upstream-clean` al commit aprobado mediante fast-forward; no usar Sync fork sobre
`main` indiscriminadamente. No hay instalación automática tras un merge.

## Evidencia y límites

Los tests comprueban cobertura, fingerprints, enlaces, empaquetado, gating textual y setup
reversible. **No prueban que un modelo obedezca las instrucciones.** El descubrimiento por
el host y los ensayos de comportamiento son estados distintos; ver `VALIDATION.md`.
`make-bot-ui` permanece condicional a un backend real; no incluye los servicios privados de Cursor.
En Antigravity el opt-in es una instrucción, no un control técnico equivalente a `openai.yaml`.

## Licencia

Se conservan la licencia MIT y los avisos de Lauren Tan en cada skill distribuida.
Los commits propios usan Conventional Commits sin trailers de atribución de IA.
