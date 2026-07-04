# Revisión clínica pendiente

Checklist para el/la profesional de salud mental que revise el contenido
curado de Rako. Todo lo listado acá fue escrito por el equipo de
desarrollo y **funciona hoy en el dispositivo**, pero no ha pasado por
revisión clínica. Ningún ítem debe editarse en código sin registrar acá
quién lo revisó y cuándo.

Contexto del producto: acompañante para estudiantes universitarios
chilenos con patrones de evasión post-trauma; **no** usuarios en crisis
activa (ese caso siempre deriva). Reglas duras en `CLAUDE.md` §4.2: en
crisis el LLM se bypassea, el sistema nunca diagnostica, nunca promete
confidencialidad absoluta, no usa frases motivacionales, siempre deriva.

| # | Ítem | Archivo | Estado |
| --- | --- | --- | --- |
| 1 | Textos de las 5 respuestas de crisis | `src/safety/responses.py` | ⬜ pendiente |
| 2 | Recursos hablados en crisis | `src/safety/resources.py` | ⬜ pendiente — **ver nota A** |
| 3 | Copy de `KEYWORDS_HARM_OTHERS` | `src/safety/responses.py` | ⬜ pendiente — **ver nota B** |
| 4 | Alerta WhatsApp al contacto de confianza | `src/channels/whatsapp/crisis_notifier.py` (`_ALERT_TEXT`) | ⬜ pendiente |
| 5 | Derivación a unidad de bienestar | `src/safety/scope.py` (`build_wellbeing_referral_response`) | ⬜ pendiente |
| 6 | Redirección de alcance clínico | `src/safety/scope.py` (`build_scope_redirect_response`) | ⬜ pendiente |
| 7 | Apoyo elevado (no-crisis) | `src/safety/scope.py` (`build_elevated_support_response`) | ⬜ pendiente |
| 8 | Follow-up post-crisis por inactividad | `src/safety/responses.py` (`inactivity_followup`) | ⬜ pendiente |
| 9 | Palabras clave de crisis (corpus) | `src/safety/detector.py` | ⬜ pendiente — **ver nota C** |
| 10 | Umbrales de triage | `src/safety/triage.py` | ⬜ pendiente — **ver nota D** |
| 11 | Ventanas del trigger de inactividad | `src/safety/detector.py` (2h / 24h) | ⬜ pendiente — **ver nota E** |
| 12 | Nota de tono para turnos con estrés académico | `src/orchestrator/prompts.py` | ⬜ pendiente |
| 13 | System prompt base del LLM | `../Rako-kb/system_prompt_rako.md` | ⬜ pendiente |
| 14 | Frases prohibidas en contenido curado | `tests/test_conversation_quality.py` (`_FORBIDDEN_PHRASES`) | ⬜ pendiente — ampliar si corresponde |

## Notas para la revisión

**Nota A — discrepancia de recursos.** El texto hablado en crisis usa
"Bienestar UDD +56 2 2820 3419" y "SAMU 131". La especificación
(`CLAUDE.md` §4.2.3) menciona "Salud Responde 600 360 7777, Línea Libre,
etc.". Salud Responde está definido en `resources.py` pero NO aparece en
el texto que el robot dice en voz alta. Decidir el set correcto (y su
orden) para: (a) crisis hablada, (b) alerta al contacto, (c) canal
WhatsApp. La alerta al contacto hoy usa Salud Responde.

**Nota B — daño a terceros.** `KEYWORDS_HARM_OTHERS` reutiliza la
respuesta de angustia auto-dirigida (`sustained_distress`) para un caso
de daño a OTROS. Probablemente requiere copy y protocolo propios
(¿deber de advertencia? ¿recursos distintos?). No tocar sin definición
profesional.

**Nota C — corpus de palabras clave.** El matcher es determinístico por
substring (auditable línea por línea, sin fuzzy matching). Cubre jerga
chilena común ("rayarme", "kiero morir") y garbles típicos de STT.
Revisar: falsos negativos esperables en el habla real de estudiantes,
falsos positivos de las exclusiones ("no quiero morir"), y qué agregar
del registro chileno actual.

**Nota D — umbrales de triage.** Ánimo bajo recurrente = ≥3 días
distintos con valencia ≤ -0.35 en 7 días (autoreporte WhatsApp) sube
cualquier mención emocional a derivación. Validar umbral y ventana.

**Nota E — trigger de inactividad.** Tras un evento de crisis o un
check-in con valencia ≤ -0.7, si pasan ≥2 horas sin interacción dentro
de las 24 h siguientes, el siguiente turno recibe el follow-up curado
(sin re-alertar al contacto). Validar ambas ventanas y el copy del
follow-up (ítem 8).

## Registro de revisiones

| Fecha | Ítems | Profesional | Resultado |
| --- | --- | --- | --- |
| — | — | — | — |
