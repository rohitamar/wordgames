import asyncio
import json
import random
import time
from dataclasses import dataclass
from itertools import count

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.rhyme_match import rhymes

TURN_SECONDS = 15
MAX_USERNAME_LENGTH = 24
MAX_GUESS_LENGTH = 64
PLACEHOLDER_WORDS = [
    "cat",
    "light",
    "stone",
    "glow",
    "train",
]


@dataclass
class ClientSession:
    websocket: WebSocket
    username: str = ""


lobby_router = APIRouter()
active_sessions: dict[int, ClientSession] = {}
session_ids = count(1)
state_lock = asyncio.Lock()
turn_task: asyncio.Task | None = None
game_state = {
    "game_started": False,
    "prompt_word": "",
    "current_turn": "",
    "current_guess": "",
    "seconds_left": TURN_SECONDS,
    "active_players": [],
    "used_words": [],
    "last_guess": None,
    "winner": "",
}


def lobby_users() -> list[str]:
    return [session.username for session in active_sessions.values() if session.username]


def can_start() -> bool:
    return len(lobby_users()) >= 2


def choose_prompt_word() -> str:
    return random.choice(PLACEHOLDER_WORDS)


def build_state_payload(session: ClientSession) -> str:
    return json.dumps(
        {
            "type": "state",
            "self_username": session.username,
            "users": lobby_users(),
            "can_start": can_start(),
            "game_started": game_state["game_started"],
            "prompt_word": game_state["prompt_word"],
            "current_turn": game_state["current_turn"],
            "current_guess": game_state["current_guess"],
            "seconds_left": game_state["seconds_left"],
            "active_players": game_state["active_players"],
            "used_words": game_state["used_words"],
            "last_guess": game_state["last_guess"],
            "winner": game_state["winner"],
        }
    )


def reset_game_state() -> None:
    game_state["game_started"] = False
    game_state["prompt_word"] = ""
    game_state["current_turn"] = ""
    game_state["current_guess"] = ""
    game_state["seconds_left"] = TURN_SECONDS
    game_state["active_players"] = []
    game_state["used_words"] = []
    game_state["last_guess"] = None
    game_state["winner"] = ""


def choose_next_player(previous_player: str | None = None) -> str:
    players = list(game_state["active_players"])
    if not players:
        return ""

    if previous_player is None:
        return players[0]

    if previous_player not in players:
        return players[0]

    previous_index = players.index(previous_player)
    return players[(previous_index + 1) % len(players)]


def finish_game(winner: str) -> None:
    game_state["game_started"] = False
    game_state["current_turn"] = ""
    game_state["current_guess"] = ""
    game_state["seconds_left"] = 0
    game_state["winner"] = winner


def username_taken(candidate: str, exclude_session_id: int | None = None) -> bool:
    for session_id, session in active_sessions.items():
        if session_id == exclude_session_id:
            continue

        if session.username == candidate:
            return True

    return False


def rename_player_references(previous_username: str, next_username: str) -> None:
    game_state["active_players"] = [
        next_username if player == previous_username else player
        for player in game_state["active_players"]
    ]

    if game_state["current_turn"] == previous_username:
        game_state["current_turn"] = next_username

    if game_state["winner"] == previous_username:
        game_state["winner"] = next_username

    last_guess = game_state["last_guess"]
    if last_guess and last_guess.get("player") == previous_username:
        last_guess["player"] = next_username


async def send_error(websocket: WebSocket, code: str, message: str) -> None:
    try:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "error",
                    "code": code,
                    "message": message,
                }
            )
        )
    except Exception:
        pass


async def cancel_turn_task() -> None:
    global turn_task

    if turn_task is None:
        return

    task = turn_task
    turn_task = None

    if task is asyncio.current_task():
        return

    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass


async def broadcast_state() -> None:
    for _, session in list(active_sessions.items()):
        try:
            await session.websocket.send_text(build_state_payload(session))
        except Exception:
            pass


async def set_next_turn(
    previous_player: str | None = None,
    cancel_existing: bool = True,
) -> None:
    global turn_task

    if cancel_existing:
        await cancel_turn_task()
    else:
        turn_task = None

    next_player = choose_next_player(previous_player)
    if not next_player:
        reset_game_state()
        await broadcast_state()
        return

    game_state["game_started"] = True
    game_state["current_turn"] = next_player
    game_state["current_guess"] = ""
    game_state["seconds_left"] = TURN_SECONDS

    await broadcast_state()
    start_turn_timer(next_player)


def start_turn_timer(expected_player: str) -> None:
    global turn_task
    turn_task = asyncio.create_task(run_turn_timer(expected_player))


async def eliminate_player(username: str) -> None:
    await cancel_turn_task()

    previous_players = list(game_state["active_players"])
    active_players = [player for player in previous_players if player != username]
    game_state["active_players"] = active_players
    game_state["current_guess"] = ""

    if len(active_players) <= 1:
        winner = active_players[0] if active_players else ""
        finish_game(winner)
        await broadcast_state()
        return

    if username in previous_players:
        next_index = previous_players.index(username)
        next_player = active_players[next_index % len(active_players)]
    else:
        next_player = active_players[0]

    game_state["game_started"] = True
    game_state["current_turn"] = next_player
    game_state["seconds_left"] = TURN_SECONDS
    await broadcast_state()
    start_turn_timer(next_player)


async def run_turn_timer(expected_player: str) -> None:
    try:
        while True:
            await asyncio.sleep(1)

            async with state_lock:
                if (
                    not game_state["game_started"]
                    or game_state["current_turn"] != expected_player
                ):
                    return

                seconds_left = int(game_state["seconds_left"])
                if seconds_left <= 1:
                    game_state["last_guess"] = {
                        "player": expected_player,
                        "word": "",
                        "correct": False,
                        "reason": "timeout",
                        "timestamp": time.time_ns(),
                    }
                    await eliminate_player(expected_player)
                    return

                game_state["seconds_left"] = seconds_left - 1
                await broadcast_state()
    except asyncio.CancelledError:
        pass


async def set_session_username(session_id: int, raw_username: object) -> None:
    session = active_sessions.get(session_id)
    if session is None:
        return

    next_username = str(raw_username or "").strip()[:MAX_USERNAME_LENGTH]
    if not next_username:
        await send_error(session.websocket, "invalid_username", "Username is required.")
        return

    if username_taken(next_username, exclude_session_id=session_id):
        await send_error(
            session.websocket,
            "username_taken",
            "That username is already in use.",
        )
        return

    previous_username = session.username
    if previous_username == next_username:
        await broadcast_state()
        return

    renamed_current_turn = previous_username and game_state["current_turn"] == previous_username

    session.username = next_username

    if previous_username and previous_username != next_username:
        rename_player_references(previous_username, next_username)

    await broadcast_state()

    if renamed_current_turn:
        await cancel_turn_task()
        start_turn_timer(next_username)


async def handle_start_game(session_id: int) -> None:
    session = active_sessions.get(session_id)
    if session is None:
        return

    if not session.username:
        await send_error(
            session.websocket,
            "username_required",
            "Choose a username before starting a round.",
        )
        return

    if game_state["game_started"]:
        return

    players = lobby_users()
    if len(players) < 2:
        await send_error(
            session.websocket,
            "not_enough_players",
            "At least two players need usernames before the game can start.",
        )
        return

    game_state["game_started"] = True
    game_state["prompt_word"] = choose_prompt_word()
    game_state["active_players"] = players
    random.shuffle(game_state["active_players"])
    game_state["used_words"] = []
    game_state["last_guess"] = None
    game_state["winner"] = ""

    await set_next_turn()


async def handle_guess_input(session_id: int, raw_value: object) -> None:
    session = active_sessions.get(session_id)
    if session is None or not session.username:
        return

    if not game_state["game_started"] or game_state["current_turn"] != session.username:
        return

    game_state["current_guess"] = str(raw_value or "")[:MAX_GUESS_LENGTH]
    await broadcast_state()


async def handle_submit_guess(session_id: int, raw_value: object) -> None:
    session = active_sessions.get(session_id)
    if session is None or not session.username:
        return

    if not game_state["game_started"] or game_state["current_turn"] != session.username:
        return

    guess = str(raw_value or "").strip()[:MAX_GUESS_LENGTH]
    game_state["current_guess"] = guess
    normalized_guess = guess.lower()

    already_used = normalized_guess in game_state["used_words"]
    does_rhyme = bool(guess) and rhymes(game_state["prompt_word"], guess)
    is_correct = bool(guess) and does_rhyme and not already_used
    reason = None

    if not guess:
        reason = "empty"
    elif already_used:
        reason = "already_used"
    elif not does_rhyme:
        reason = "not_rhyme"

    if is_correct:
        game_state["used_words"].append(normalized_guess)

    game_state["last_guess"] = {
        "player": session.username,
        "word": guess,
        "correct": is_correct,
        "reason": reason,
        "timestamp": time.time_ns(),
    }

    if is_correct:
        await set_next_turn(session.username)
        return

    await broadcast_state()


async def remove_session(session_id: int) -> None:
    session = active_sessions.pop(session_id, None)
    if session is None:
        return

    username = session.username

    if not active_sessions:
        await cancel_turn_task()
        reset_game_state()
        return

    if username and username in game_state["active_players"]:
        if game_state["current_turn"] == username:
            await eliminate_player(username)
            return

        game_state["active_players"] = [
            player for player in game_state["active_players"] if player != username
        ]

        if len(game_state["active_players"]) == 1:
            await cancel_turn_task()
            finish_game(game_state["active_players"][0])
            await broadcast_state()
            return

    if username and not game_state["game_started"] and game_state["winner"] == username:
        game_state["winner"] = ""

    await broadcast_state()


@lobby_router.websocket("/ws")
async def lobby_connection(websocket: WebSocket) -> None:
    await websocket.accept()

    session_id = next(session_ids)

    async with state_lock:
        active_sessions[session_id] = ClientSession(websocket=websocket)
        await broadcast_state()

    try:
        while True:
            raw_message = await websocket.receive_text()

            try:
                data = json.loads(raw_message)
            except json.JSONDecodeError:
                await send_error(websocket, "invalid_payload", "Malformed JSON payload.")
                continue

            message_type = data.get("type")

            async with state_lock:
                if session_id not in active_sessions:
                    return

                if message_type == "set_username":
                    await set_session_username(session_id, data.get("value"))
                    continue

                if message_type == "start_game":
                    await handle_start_game(session_id)
                    continue

                if message_type == "guess_input":
                    await handle_guess_input(session_id, data.get("value"))
                    continue

                if message_type == "submit_guess":
                    await handle_submit_guess(session_id, data.get("value"))
                    continue

                await send_error(websocket, "unknown_event", "Unknown message type.")
    except WebSocketDisconnect:
        pass
    finally:
        async with state_lock:
            await remove_session(session_id)
