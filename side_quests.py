"""
Side Quests: misiones semanales por mensaje directo en Slack.

Tres comandos:
    python side_quests.py abrir      -> publica y fija el mensaje de suscripción
    python side_quests.py asignar    -> lunes: manda una misión al azar a cada suscriptor
    python side_quests.py resumen    -> viernes: publica quiénes la completaron

Nadie entra por defecto. Se suscribe quien reacciona con el emoji del dragón
al mensaje fijado, y se va cuando quita la reacción.
"""

import json
import os
import pathlib
import random
import sys
import datetime
import urllib.parse
import urllib.request

SLACK_API = "https://slack.com/api/"
ROOT = pathlib.Path(__file__).parent
MISSIONS_FILE = ROOT / "missions.json"
STATE_DIR = ROOT / "assignments"
SUBSCRIPTION_FILE = ROOT / "subscription.json"

# Cuántas semanas hacia atrás evitamos repetirle una misión a la misma persona.
NO_REPEAT_WEEKS = 8

# Emoji para entrar a Side Quests (la espada, en el mensaje fijado del canal).
JOIN_EMOJI = os.environ.get("JOIN_EMOJI", "dagger_knife")

# Emojis que cuentan como "misión completada" en el DM. Cualquiera de los tres vale,
# para que nadie quede afuera por marcar con el check de siempre.
DONE_EMOJIS = [
    e.strip()
    for e in os.environ.get(
        "DONE_EMOJIS", "crossed_swords,white_check_mark,heavy_check_mark"
    ).split(",")
    if e.strip()
]


# ---------------------------------------------------------------- Slack API

def slack(method, payload=None, as_json=False):
    """Llama a un método de la API de Slack y devuelve la respuesta ya parseada."""
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        sys.exit("Falta la variable SLACK_BOT_TOKEN.")

    payload = payload or {}
    headers = {"Authorization": "Bearer " + token}

    if as_json:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    else:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    req = urllib.request.Request(SLACK_API + method, data=data, headers=headers)
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    if not body.get("ok"):
        raise RuntimeError("Slack respondió error en %s: %s" % (method, body.get("error")))
    return body


def channel():
    value = os.environ.get("SIDE_QUESTS_CHANNEL")
    if not value:
        sys.exit("Falta la variable SIDE_QUESTS_CHANNEL (ID del canal, tipo C0123ABCD).")
    return value


def is_person(user_id):
    """Descarta bots y cuentas desactivadas."""
    if user_id == "USLACKBOT":
        return False
    info = slack("users.info", {"user": user_id})["user"]
    return not info.get("is_bot") and not info.get("deleted")


# -------------------------------------------------------- Fase 0: suscripción

INVITACION = (
    ":dragon: *Side Quests*\n\n"
    "Cada lunes te llega por mensaje directo una misión corta y al azar. "
    "Nadie sabe qué le tocó al resto hasta el viernes.\n\n"
    "Son cosas cortas y casi siempre fuera de la pantalla: caminar, cocinar algo, "
    "hablar con alguien. No es trabajo extra disfrazado de juego.\n\n"
    "Toma tu espada: reacciona a este mensaje con :%s: para entrar. "
    "Quita la reacción cuando quieras salir, sin avisar y sin que nadie pregunte."
)


def abrir():
    """Publica el mensaje de suscripción, lo fija y guarda su referencia."""
    posted = slack(
        "chat.postMessage",
        {"channel": channel(), "text": INVITACION % JOIN_EMOJI, "unfurl_links": False},
        as_json=True,
    )
    try:
        slack("pins.add", {"channel": posted["channel"], "timestamp": posted["ts"]})
    except RuntimeError as error:
        print("Aviso: no pude fijar el mensaje (%s). Fíjalo a mano." % error)

    SUBSCRIPTION_FILE.write_text(
        json.dumps({"channel": posted["channel"], "ts": posted["ts"]}, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Mensaje de suscripción publicado. Ahora la gente puede entrar con :%s:." % JOIN_EMOJI)


def subscribers():
    """Quiénes reaccionaron con el emoji de entrada al mensaje fijado."""
    if not SUBSCRIPTION_FILE.exists():
        sys.exit("No hay mensaje de suscripción. Corre primero: python side_quests.py abrir")

    ref = json.loads(SUBSCRIPTION_FILE.read_text(encoding="utf-8"))
    body = slack(
        "reactions.get",
        {"channel": ref["channel"], "timestamp": ref["ts"], "full": "true"},
    )
    people = []
    for reaction in body.get("message", {}).get("reactions", []):
        if reaction["name"] != JOIN_EMOJI:
            continue
        for user_id in reaction.get("users", []):
            if user_id not in people and is_person(user_id):
                people.append(user_id)
    return people


# ------------------------------------------------------------ Estado semanal

def week_key(today=None):
    today = today or datetime.date.today()
    year, week, _ = today.isocalendar()
    return "%d-W%02d" % (year, week)


def load_missions():
    missions = json.loads(MISSIONS_FILE.read_text(encoding="utf-8"))
    if not missions:
        sys.exit("missions.json está vacío.")
    return missions


def recent_history():
    """Devuelve {user_id: [mission_id, ...]} con las misiones de las últimas semanas."""
    if not STATE_DIR.exists():
        return {}
    files = sorted(STATE_DIR.glob("2*.json"))[-NO_REPEAT_WEEKS:]
    history = {}
    for path in files:
        week = json.loads(path.read_text(encoding="utf-8"))
        for record in week.get("assignments", []):
            history.setdefault(record["user"], []).append(record["mission_id"])
    return history


def pick_mission(missions, already_done):
    """Elige al azar, pero priorizando las misiones que esta persona no tuvo."""
    fresh = [m for m in missions if m["id"] not in already_done]
    return random.choice(fresh or missions)


# ------------------------------------------------------- Fase 1: misión (lun)

BIENVENIDA = (
    ":dragon: Tomaste la espada, así que esta es tu primera misión. "
    "Bienvenida al gremio.\n\n"
)

MISION = (
    ":dagger_knife: *Tu Side Quest de la semana*\n\n"
    "> %s\n\n"
    "Tienes hasta el viernes. Cuando la completes, reacciona a este mensaje con :%s:.\n\n"
    "El viernes publico en el canal quiénes lo lograron, nunca qué le tocó a cada quien. "
    "Eso queda entre tú y el dragón."
)


def asignar():
    missions = load_missions()
    history = recent_history()
    people = subscribers()

    if not people:
        print("Todavía no hay nadie suscrito. No mando nada.")
        return

    records = []
    for user_id in people:
        mission = pick_mission(missions, history.get(user_id, []))
        dm = slack("conversations.open", {"users": user_id})["channel"]["id"]

        text = MISION % (mission["text"], DONE_EMOJIS[0])
        if user_id not in history:
            text = BIENVENIDA + text

        posted = slack(
            "chat.postMessage",
            {"channel": dm, "text": text, "unfurl_links": False},
            as_json=True,
        )
        records.append(
            {
                "user": user_id,
                "mission_id": mission["id"],
                "mission": mission["text"],
                "dm_channel": dm,
                "ts": posted["ts"],
            }
        )
        print("Misión enviada a %s: %s" % (user_id, mission["id"]))

    STATE_DIR.mkdir(exist_ok=True)
    out = STATE_DIR / ("%s.json" % week_key())
    out.write_text(
        json.dumps(
            {
                "week": week_key(),
                "sent_at": datetime.date.today().isoformat(),
                "assignments": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("Guardado %s con %d %s." % (out.name, len(records),
                                     "misión" if len(records) == 1 else "misiones"))


# ------------------------------------------------------ Fase 2: resumen (vie)

def completed(record):
    """True si esa persona reaccionó a su propio DM con alguno de los emojis válidos."""
    body = slack(
        "reactions.get",
        {"channel": record["dm_channel"], "timestamp": record["ts"], "full": "true"},
    )
    for reaction in body.get("message", {}).get("reactions", []):
        if reaction["name"] in DONE_EMOJIS and record["user"] in reaction.get("users", []):
            return True
    return False


def summary_text(winners, total):
    lista = "\n".join("• <@%s>" % user for user in winners)

    if not winners:
        return (
            ":dragon: *Side Quests de la semana*\n\n"
            "Esta semana ganó el dragón. Nadie completó su misión.\n\n"
            "Pasa. El lunes hay otra y arrancamos de cero."
        )

    if len(winners) == total:
        return (
            ":crossed_swords: *Side Quests de la semana*\n\n"
            "%s\n\n"
            "Las %d misiones cayeron. El dragón está ofendido y el lunes vuelve con más."
            % (lista, total)
        )

    return (
        ":crossed_swords: *Side Quests de la semana*\n\n"
        "%s\n\n"
        "%d de %d completaron su misión. El dragón sigue vivo, lo intentamos el lunes."
        % (lista, len(winners), total)
    )


def resumen():
    path = STATE_DIR / ("%s.json" % week_key())
    if not path.exists():
        print("No hay misiones registradas para la semana %s. No publico nada." % week_key())
        return

    records = json.loads(path.read_text(encoding="utf-8"))["assignments"]
    winners = [r["user"] for r in records if completed(r)]

    slack(
        "chat.postMessage",
        {"channel": channel(), "text": summary_text(winners, len(records))},
        as_json=True,
    )
    print("Resumen publicado: %d de %d." % (len(winners), len(records)))


COMMANDS = {
    "abrir": abrir,
    "asignar": asignar,
    "resumen": resumen,
    # alias en inglés, por si alguien forkea el repo
    "open": abrir,
    "assign": asignar,
    "summary": resumen,
}

if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command not in COMMANDS:
        sys.exit("Uso: python side_quests.py [abrir|asignar|resumen]")
    COMMANDS[command]()
