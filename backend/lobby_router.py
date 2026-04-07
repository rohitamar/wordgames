import asyncio
import json
import random
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from services.rhyme_match import rhymes

TURN_SECONDS = 15
PLACEHOLDER_WORDS = [
    "cat",
    "light",
    "stone",
    "glow",
    "train",
]

lobby_router = APIRouter()
active_connections: dict[str, WebSocket] = {}
sse_subscribers: set[asyncio.Queue[str]] = set()
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
    return list(active_connections.keys())

def can_start() -> bool:
    return len(active_connections) >= 2

def choose_prompt_word() -> str:
    return random.choice(PLACEHOLDER_WORDS)

def build_lobby_state() -> str:
    return json.dumps(
        {
            "type": "lobby_state",
            "users": lobby_users(),
            "can_start": can_start(),
        }
    )

def build_game_state() -> str:
    return json.dumps({
        "type": "game_state",
        "users": lobby_users(),
        "game_started": game_state["game_started"],
        "prompt_word": game_state["prompt_word"],
        "current_turn": game_state["current_turn"],
        "current_guess": game_state["current_guess"],
        "seconds_left": game_state["seconds_left"],
        "active_players": game_state["active_players"],
        "used_words": game_state["used_words"],
        "last_guess": game_state["last_guess"],
        "winner": game_state["winner"],
        "can_start": can_start()
    })

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


async def eliminate_player(username: str) -> None:
    await cancel_turn_task()

    previous_players = list(game_state["active_players"])
    active_players = [player for player in previous_players if player != username]
    game_state["active_players"] = active_players
    game_state["current_guess"] = ""

    if len(active_players) <= 1:
        winner = active_players[0] if active_players else ""
        finish_game(winner)
        await sync_broadcasts()
        return

    if username in previous_players:
        next_index = previous_players.index(username)
        next_player = active_players[next_index % len(active_players)]
    else:
        next_player = active_players[0]

    game_state["game_started"] = True
    game_state["current_turn"] = next_player
    game_state["seconds_left"] = TURN_SECONDS
    await sync_broadcasts()
    start_turn_timer(next_player)

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

async def broadcast_lobby_state() -> None:
    message = build_lobby_state()
    sse_message = f"data: {message}\n\n"
    disconnected_users = []
    disconnected_subscribers = []

    for username, websocket in active_connections.items():
        try:
            await websocket.send_text(message)
        except Exception:
            disconnected_users.append(username)

    for username in disconnected_users:
        active_connections.pop(username, None)

    for queue in sse_subscribers:
        try:
            queue.put_nowait(sse_message)
        except Exception:
            disconnected_subscribers.append(queue)

    for queue in disconnected_subscribers:
        sse_subscribers.discard(queue)

async def broadcast_game_state() -> None:
    message = build_game_state()
    disconnected_users = []

    for username, websocket in active_connections.items():
        try:
            await websocket.send_text(message)
        except Exception:
            disconnected_users.append(username)

    for username in disconnected_users:
        active_connections.pop(username, None)

async def sync_broadcasts() -> None:
    await broadcast_lobby_state()
    await broadcast_game_state()

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
        await sync_broadcasts()
        return

    game_state["game_started"] = True
    game_state["current_turn"] = next_player
    game_state["current_guess"] = ""
    game_state["seconds_left"] = TURN_SECONDS

    await sync_broadcasts()
    start_turn_timer(next_player)


def start_turn_timer(expected_player: str) -> None:
    global turn_task
    turn_task = asyncio.create_task(run_turn_timer(expected_player))

async def run_turn_timer(expected_player: str) -> None:
    try:
        while True:
            await asyncio.sleep(1)

            async with state_lock:
                if not game_state["game_started"] or game_state["current_turn"] != expected_player:
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
                await broadcast_game_state()
    except asyncio.CancelledError:
        pass

@lobby_router.get("/lobby/stream")
async def stream_lobby() -> StreamingResponse:
    queue: asyncio.Queue[str] = asyncio.Queue()
    sse_subscribers.add(queue)

    async def event_stream() -> AsyncIterator[str]:
        try:
            yield f"data: {build_lobby_state()}\n\n"
            while True:
                message = await queue.get()
                yield message
        finally:
            sse_subscribers.discard(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

@lobby_router.websocket("/ws/{username}")
async def lobby_connection(websocket: WebSocket, username: str) -> None:
    await websocket.accept()

    async with state_lock:
        if username in active_connections:
            await websocket.close(code=1008, reason="Username already taken")
            return

        active_connections[username] = websocket
        await sync_broadcasts()

    try:
        while True:
            raw_message = await websocket.receive_text()
            data = json.loads(raw_message)
            message_type = data.get("type")

            async with state_lock:
                if message_type == "start_game":
                    if len(active_connections) < 2:
                        continue

                    game_state["game_started"] = True
                    game_state["prompt_word"] = choose_prompt_word()
                    shuffled_players = lobby_users()
                    random.shuffle(shuffled_players)
                    game_state["active_players"] = shuffled_players
                    game_state["used_words"] = []
                    game_state["last_guess"] = None
                    game_state["winner"] = ""
                    await set_next_turn()
                    continue

                if message_type == "guess_input":
                    if game_state["current_turn"] != username:
                        continue

                    game_state["current_guess"] = str(data.get("value", ""))[:64]
                    await broadcast_game_state()
                    continue

                if message_type == "submit_guess":
                    if game_state["current_turn"] != username:
                        continue

                    guess = str(data.get("value", "")).strip()
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
                        "player": username,
                        "word": guess,
                        "correct": is_correct,
                        "reason": reason,
                        "timestamp": time.time_ns(),
                    }

                    if is_correct:
                        await set_next_turn(username)
                    else:
                        await broadcast_game_state()
    except WebSocketDisconnect:
        pass
    finally:
        async with state_lock:
            active_connections.pop(username, None)

            if username in game_state["active_players"]:
                game_state["active_players"] = [
                    player for player in game_state["active_players"] if player != username
                ]

            if not active_connections:
                await cancel_turn_task()
                reset_game_state()
                await sync_broadcasts()
            elif len(game_state["active_players"]) == 1:
                await cancel_turn_task()
                finish_game(game_state["active_players"][0])
                await sync_broadcasts()
            elif not game_state["active_players"] and game_state["winner"]:
                await sync_broadcasts()
            elif game_state["current_turn"] == username:
                await set_next_turn(username)
            else:
                await sync_broadcasts()
