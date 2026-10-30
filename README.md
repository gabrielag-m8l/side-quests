# Side Quests

Un bot de Slack que cada lunes le manda una misión corta y al azar, por mensaje directo, a quien se haya suscrito. El viernes publica en el canal quiénes la completaron.

Nadie entra por defecto. Se suscribe quien reacciona con 🗡️ a un mensaje fijado en el canal, y se va cuando quita la reacción.

La gracia está en que la misión llega por DM. Nadie sabe qué le tocó al resto hasta el viernes, y el resumen nunca dice qué misión tuvo cada quien.

No necesita servidor ni base de datos. Corre con GitHub Actions, que es gratis.

## Cómo funciona

1. **Una vez**: el bot publica y fija en el canal un mensaje explicando Side Quests. Quien quiere entrar reacciona con 🗡️.
2. **Lunes**: lee esas reacciones, le manda a cada suscriptor una misión al azar por DM y guarda lo asignado en `assignments/2026-W44.json`.
3. **Durante la semana**: quien completa su misión reacciona a su propio DM con ⚔️ (también valen ✅ y ✔️).
4. **Viernes**: revisa las reacciones y publica la lista de quienes lo lograron.

El dragón es el rival de la historia, no una reacción: aparece en los textos y gana la semana en que nadie completa su misión.

El bot nunca repite una misión que esa persona ya haya tenido en las últimas 8 semanas.

## Instalación

### 1. Crea la app de Slack

Entra a [api.slack.com/apps](https://api.slack.com/apps), elige **Create New App → From a manifest**, selecciona tu workspace y pega el contenido de `slack-app-manifest.yml`.

Después ve a **OAuth & Permissions**, instala la app en el workspace y copia el **Bot User OAuth Token** (empieza con `xoxb-`).

### 2. Invita al bot al canal

En el canal donde quieras el mensaje de suscripción y el resumen de los viernes:

```
/invite @Side Quests
```

Para conseguir el ID del canal: clic derecho en el canal → **Copiar enlace**. El ID es la parte que empieza con `C`, por ejemplo `C0123ABCD`.

### 3. Configura el repositorio

Haz un fork o clona este repositorio en tu cuenta. Luego ve a **Settings → Secrets and variables → Actions** y agrega:

| Tipo | Nombre | Valor |
|---|---|---|
| Secret | `SLACK_BOT_TOKEN` | el token `xoxb-...` |
| Secret | `SIDE_QUESTS_CHANNEL` | el ID del canal, tipo `C0123ABCD` |
| Variable (opcional) | `JOIN_EMOJI` | emoji para entrar. Por defecto `dagger_knife` (🗡️) |
| Variable (opcional) | `DONE_EMOJIS` | emojis que cuentan como completada, separados por coma. Por defecto `crossed_swords,white_check_mark,heavy_check_mark` |

### 4. Abre las suscripciones

En la pestaña **Actions**, abre "Publicar mensaje de suscripción" y dale a **Run workflow**. El bot publica el mensaje en el canal, lo fija y guarda su referencia en `subscription.json`.

Reacciona tú con 🗡️ y después corre "Enviar misiones (lunes)" a mano para probar. Deberías recibir tu misión por DM en unos segundos.

Si alguna vez quieres volver a empezar, corre ese workflow otra vez: el mensaje nuevo reemplaza al anterior y las suscripciones arrancan de cero.

## Si algo falla

El bot avisa el error exacto que devolvió Slack. Los dos más probables:

- `missing_scope`: falta un permiso. Vuelve a **OAuth & Permissions**, agrega el que nombra el error y reinstala la app. Según la configuración del workspace, leer reacciones puede pedir también `channels:history` (o `groups:history` si el canal es privado) e `im:history`.
- `not_in_channel`: el bot no está en el canal. Corre `/invite @Side Quests` ahí.

Si cambias de canal, corre otra vez el workflow de suscripción: `subscription.json` apunta al mensaje viejo.

## Horarios

Los crons están en UTC para que caigan lunes 10:00 y viernes 17:00 hora de Buenos Aires (UTC-3). Si estás en otra zona, edita las líneas `cron:` en `.github/workflows/`.

GitHub a veces demora los workflows programados unos minutos cuando hay mucha carga. Para esto no importa.

## Personalizar las misiones

Edita `missions.json`. Cada misión necesita un `id` único y un `text`:

```json
{ "id": "cafe-random", "text": "Invita a alguien del equipo con quien casi nunca hablas a un café de 15 minutos." }
```

Las 20 que vienen por defecto están pensadas para equipos remotos o híbridos: mezclan cosas sociales, de aprendizaje y de higiene de trabajo. Cámbialas por las tuyas, mientras más específicas del equipo, mejor funcionan.

Los textos del bot están arriba de cada sección en `side_quests.py`, en las constantes `INVITACION`, `BIENVENIDA`, `MISION` y la función `summary_text`. Si tu equipo trabaja en inglés, tradúcelos junto con `missions.json`.

## Correrlo a mano

```bash
export SLACK_BOT_TOKEN="xoxb-..."
export SIDE_QUESTS_CHANNEL="C0123ABCD"

python side_quests.py abrir     # publica el mensaje de suscripción
python side_quests.py asignar   # manda las misiones
python side_quests.py resumen   # publica el resumen
```

Solo necesita Python 3.9 o superior. No hay dependencias externas, todo va con la librería estándar.

## Qué guarda y qué no

`subscription.json` guarda el canal y la marca de tiempo del mensaje fijado. `assignments/2026-W44.json` guarda IDs de usuario de Slack, qué misión le tocó a cada quien y la marca de tiempo de su DM.

El bot nunca lee el contenido de tus conversaciones. Solo las reacciones a dos cosas: el mensaje de suscripción y los mensajes que él mismo mandó.

Si tu repositorio es público, esos IDs quedan visibles. Son identificadores internos de Slack, no nombres ni correos, pero si prefieres evitarlo usa un repositorio privado. GitHub Actions también es gratis ahí, con un tope mensual de minutos que este bot no se acerca a gastar.

## Ideas para después

- Un comando para que la gente proponga misiones nuevas.
- Rachas: quién completó más semanas seguidas.
- Misiones distintas según el equipo o el rol.

Si lo usas y le haces cambios, me encantaría verlos.

## Licencia

MIT. Haz lo que quieras con esto.
