import { useEffect, useRef, useState } from "react";

export default function App() {
    const [usernameInput, setUsernameInput] = useState("");
    const [submittedUsername, setSubmittedUsername] = useState("");
    const [isEditing, setIsEditing] = useState(true);
    const [connectionStatus, setConnectionStatus] = useState("disconnected");
    const [lobbyUsers, setLobbyUsers] = useState([]);
    const [gameStarted, setGameStarted] = useState(false);
    const [promptWord, setPromptWord] = useState("");
    const [currentTurn, setCurrentTurn] = useState("");
    const [currentGuess, setCurrentGuess] = useState("");
    const [secondsLeft, setSecondsLeft] = useState(15);
    const [activePlayers, setActivePlayers] = useState([]);
    const [winner, setWinner] = useState("");
    const [lastGuess, setLastGuess] = useState(null);
    const [guessLog, setGuessLog] = useState([]);
    const [guessInput, setGuessInput] = useState("");
    const socketRef = useRef(null);
    const lastLoggedGuessTimestampRef = useRef(null);

    useEffect(() => {
        const eventSource = new EventSource("http://localhost:8000/lobby/stream");

        eventSource.onmessage = (event) => {
            try {
                const parsedMessage = JSON.parse(event.data);

                if (Array.isArray(parsedMessage.users)) {
                    setLobbyUsers(parsedMessage.users);
                }
            } catch (error) {
                console.error("Failed to parse lobby stream message:", error);
            }
        };

        eventSource.onerror = (error) => {
            console.error("Lobby stream error:", error);
        };

        return () => {
            eventSource.close();
        };
    }, []);

    const closeSocket = () => {
        const socket = socketRef.current;
        if (!socket) {
            return;
        }

        socketRef.current = null;

        try {
            socket.close();
        } catch {
            // Ignore close errors during reconnects or unmount.
        }
    };

    const resetGameView = () => {
        setGameStarted(false);
        setPromptWord("");
        setCurrentTurn("");
        setCurrentGuess("");
        setSecondsLeft(15);
        setActivePlayers([]);
        setWinner("");
        setLastGuess(null);
        setGuessLog([]);
        setGuessInput("");
        lastLoggedGuessTimestampRef.current = null;
    };

    useEffect(() => {
        return () => {
            closeSocket();
        };
    }, []);

    useEffect(() => {
        if (!gameStarted || currentTurn !== submittedUsername) {
            setGuessInput("");
        } else {
            setGuessInput(currentGuess);
        }
    }, [currentGuess, currentTurn, gameStarted, submittedUsername]);

    useEffect(() => {
        if (!lastGuess?.timestamp) {
            return;
        }

        if (lastLoggedGuessTimestampRef.current === lastGuess.timestamp) {
            return;
        }

        lastLoggedGuessTimestampRef.current = lastGuess.timestamp;
        setGuessLog((previousLog) => [
            ...previousLog,
            {
                timestamp: lastGuess.timestamp,
                player: lastGuess.player,
                word: lastGuess.word || "...",
                connective: lastGuess.correct
                    ? ", and"
                    : lastGuess.reason === "already_used"
                        ? ", but"
                        : ", and",
                outcome: lastGuess.correct
                    ? "it rhymed."
                    : lastGuess.reason === "already_used"
                        ? "that word was already used."
                        : lastGuess.reason === "timeout"
                            ? "timed out."
                            : "it did not rhyme.",
                correct: Boolean(lastGuess.correct),
                timedOut: lastGuess.reason === "timeout",
            },
        ]);
    }, [lastGuess]);

    const connectSocket = (trimmedUsername) => {
        closeSocket();
        resetGameView();
        setConnectionStatus("connecting");

        const socket = new WebSocket(
            `ws://localhost:8000/ws/${encodeURIComponent(trimmedUsername)}`
        );
        socketRef.current = socket;

        socket.onopen = () => {
            if (socketRef.current !== socket) {
                return;
            }

            setConnectionStatus("connected");
            setSubmittedUsername(trimmedUsername);
            setIsEditing(false);
        };

        socket.onmessage = (event) => {
            if (socketRef.current !== socket) {
                return;
            }

            const messageText =
                typeof event.data === "string" ? event.data : String(event.data);

            console.log("WebSocket message:", event.data);

            try {
                const parsedMessage = JSON.parse(messageText);

                if (
                    parsedMessage.type === "lobby_state" &&
                    Array.isArray(parsedMessage.users)
                ) {
                    setLobbyUsers(parsedMessage.users);
                }

                if (parsedMessage.type === "game_state") {
                    setLobbyUsers(
                        Array.isArray(parsedMessage.users) ? parsedMessage.users : []
                    );
                    setGameStarted(Boolean(parsedMessage.game_started));
                    setPromptWord(parsedMessage.prompt_word ?? "");
                    setCurrentTurn(parsedMessage.current_turn ?? "");
                    setCurrentGuess(parsedMessage.current_guess ?? "");
                    setSecondsLeft(
                        Number.isFinite(parsedMessage.seconds_left)
                            ? parsedMessage.seconds_left
                            : 15
                    );
                    setActivePlayers(
                        Array.isArray(parsedMessage.active_players)
                            ? parsedMessage.active_players
                            : []
                    );
                    setWinner(parsedMessage.winner ?? "");
                    setLastGuess(parsedMessage.last_guess ?? null);
                }
            } catch {
                // Ignore malformed messages in the MVP client.
            }
        };

        socket.onclose = () => {
            if (socketRef.current !== socket) {
                return;
            }

            socketRef.current = null;
            setConnectionStatus("disconnected");
            resetGameView();
        };

        socket.onerror = (error) => {
            if (socketRef.current !== socket) {
                return;
            }

            console.error("WebSocket error:", error);
        };
    };

    const handleSubmit = (event) => {
        event.preventDefault();

        const trimmedUsername = usernameInput.trim();
        if (!trimmedUsername) {
            return;
        }

        connectSocket(trimmedUsername);
    };

    const handleEdit = () => {
        setUsernameInput(submittedUsername);
        setIsEditing(true);
    };

    const handleStartGame = () => {
        const socket = socketRef.current;
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            return;
        }

        socket.send(JSON.stringify({ type: "start_game" }));
    };

    const handleGuessChange = (event) => {
        const nextGuess = event.target.value;
        setGuessInput(nextGuess);

        const socket = socketRef.current;
        if (
            !socket ||
            socket.readyState !== WebSocket.OPEN ||
            submittedUsername !== currentTurn
        ) {
            return;
        }

        socket.send(JSON.stringify({ type: "guess_input", value: nextGuess }));
    };

    const handleGuessSubmit = (event) => {
        event.preventDefault();

        const socket = socketRef.current;
        const guess = guessInput.trim();
        if (
            !socket ||
            socket.readyState !== WebSocket.OPEN ||
            submittedUsername !== currentTurn ||
            !guess
        ) {
            return;
        }

        socket.send(JSON.stringify({ type: "submit_guess", value: guess }));
    };

    const isCurrentTurn = submittedUsername !== "" && submittedUsername === currentTurn;
    const activeTypingLabel = currentGuess || "Nothing yet";
    const showRoundState = gameStarted || Boolean(winner);
    const canStartGame = connectionStatus === "connected" && lobbyUsers.length >= 2;
    const showStartButton = !gameStarted;

    return (
        <main style={styles.page}>
            <h1 style={styles.cornerTitle}>Word Games</h1>

            <aside style={styles.lobbyPanel}>
                <p style={styles.lobbyTitle}>Lobby</p>
                {lobbyUsers.map((user) => (
                    <p
                        key={user}
                        style={{
                            ...styles.lobbyUser,
                            ...(showRoundState
                                ? activePlayers.includes(user)
                                    ? styles.lobbyUserActive
                                    : styles.lobbyUserInactive
                                : {}),
                        }}
                    >
                        {user}
                    </p>
                ))}
            </aside>

            {!gameStarted && !winner ? (
                <section style={styles.card}>
                    {isEditing ? (
                        <form onSubmit={handleSubmit} style={styles.form}>
                            <input
                                autoComplete="off"
                                autoFocus
                                onChange={(event) => setUsernameInput(event.target.value)}
                                placeholder="Username"
                                style={styles.input}
                                value={usernameInput}
                            />
                            <button style={styles.button} type="submit">
                                Submit
                            </button>
                        </form>
                    ) : (
                        <div style={styles.usernameRow}>
                            <span style={styles.usernameText}>{submittedUsername}</span>
                            <button
                                onClick={handleEdit}
                                style={{ ...styles.button, ...styles.editButton }}
                                type="button"
                            >
                                Edit
                            </button>
                        </div>
                    )}

                    <button
                        disabled={!canStartGame}
                        onClick={handleStartGame}
                        style={{
                            ...styles.button,
                            ...(!canStartGame ? styles.buttonDisabled : {}),
                            marginTop: 8,
                        }}
                        type="button"
                    >
                        Start Game
                    </button>
                </section>
            ) : (
                <section style={styles.gameCard}>
                    {winner ? (
                        <p style={styles.winnerText}>{winner} wins the round.</p>
                    ) : null}

                    {showStartButton ? (
                        <button
                            disabled={!canStartGame}
                            onClick={handleStartGame}
                            style={{
                                ...styles.button,
                                ...(!canStartGame ? styles.buttonDisabled : {}),
                            }}
                            type="button"
                        >
                            Start Game
                        </button>
                    ) : null}

                    <p style={styles.promptWord}>{promptWord || "Loading..."}</p>

                    {!winner ? (
                        <>
                            <p style={styles.metaText}>
                                Current turn: {currentTurn || "Waiting..."}
                            </p>
                            <p style={styles.metaText}>Timer: {secondsLeft}s</p>
                            <p style={styles.metaText}>
                                {currentTurn || "Nobody"} is typing: {activeTypingLabel}
                            </p>
                        </>
                    ) : null}

                    {!winner ? (
                        <form onSubmit={handleGuessSubmit} style={styles.guessForm}>
                            <input
                                disabled={!isCurrentTurn}
                                onChange={handleGuessChange}
                                placeholder={
                                    isCurrentTurn
                                        ? "Type a rhyming word"
                                        : "Waiting for the active player"
                                }
                                style={styles.input}
                                value={guessInput}
                            />
                            <button
                                disabled={!isCurrentTurn}
                                style={{
                                    ...styles.button,
                                    ...(!isCurrentTurn ? styles.buttonDisabled : {}),
                                }}
                                type="submit"
                            >
                                Guess
                            </button>
                        </form>
                    ) : null}

                    <section style={styles.logPanel}>
                        {guessLog.length > 0 ? (
                            guessLog.map((entry) => (
                                <p key={entry.timestamp} style={styles.logEntry}>
                                    <span style={styles.logPlayer}>{entry.player}</span>
                                    {entry.timedOut ? (
                                        <span> timed out.</span>
                                    ) : (
                                        <>
                                            <span> guessed "{entry.word}"</span>
                                            {entry.connective ? <span>{entry.connective} </span> : null}
                                            <span
                                                style={
                                                    entry.correct
                                                        ? styles.logSuccess
                                                        : styles.logError
                                                }
                                            >
                                                {entry.outcome}
                                            </span>
                                        </>
                                    )}
                                </p>
                            ))
                        ) : (
                            <p style={styles.logEntry}>No guesses yet.</p>
                        )}
                    </section>
                </section>
            )}
        </main>
    );
}

const styles = {
    page: {
        position: "fixed",
        inset: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#ffffff",
        padding: 16,
        boxSizing: "border-box",
    },
    cornerTitle: {
        position: "absolute",
        top: 20,
        left: 24,
        margin: 0,
        fontSize: 26,
        fontWeight: 600,
        color: "#333333",
    },
    lobbyPanel: {
        position: "absolute",
        top: 20,
        right: 24,
        minWidth: 120,
        textAlign: "right",
    },
    lobbyTitle: {
        margin: "0 0 8px",
        fontSize: 18,
        fontWeight: 600,
        color: "#555555",
    },
    lobbyUser: {
        margin: "0 0 4px",
        fontSize: 16,
        color: "#777777",
    },
    lobbyUserActive: {
        color: "#2e8b57",
    },
    lobbyUserInactive: {
        color: "#c0392b",
    },
    card: {
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
        width: "min(360px, 100%)",
        textAlign: "center",
        transform: "translateY(-24px)",
    },
    gameCard: {
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 10,
        width: "min(460px, 100%)",
        textAlign: "center",
        transform: "translateY(-88px)",
    },
    form: {
        display: "flex",
        gap: 6,
        width: "100%",
    },
    usernameRow: {
        display: "flex",
        gap: 12,
        alignItems: "center",
        justifyContent: "center",
        width: "auto",
        maxWidth: "100%",
        margin: "0 auto",
    },
    guessForm: {
        display: "flex",
        gap: 8,
        width: "100%",
    },
    input: {
        flex: 1,
        minWidth: 0,
        padding: "10px 12px",
        border: "1px solid #d9d9d9",
        borderRadius: 3,
        fontSize: 16,
        color: "#444444",
        backgroundColor: "#ffffff",
    },
    button: {
        padding: "9px 12px",
        border: "1px solid #d9d9d9",
        borderRadius: 3,
        backgroundColor: "#ffffff",
        color: "#555555",
        fontSize: 14,
        cursor: "pointer",
    },
    editButton: {
        padding: "3px 8px",
        lineHeight: 1.2,
        transform: "translateY(2px)",
    },
    buttonDisabled: {
        color: "#aaaaaa",
        cursor: "not-allowed",
    },
    usernameText: {
        padding: "8px 0",
        fontSize: 18,
        color: "#444444",
        textAlign: "center",
        wordBreak: "break-word",
    },
    promptWord: {
        margin: 0,
        fontSize: 46,
        color: "#333333",
    },
    winnerText: {
        margin: 0,
        fontSize: 22,
        fontWeight: 600,
        color: "#333333",
    },
    metaText: {
        margin: 0,
        fontSize: 16,
        color: "#666666",
    },
    logPanel: {
        width: "100%",
        maxHeight: 170,
        overflowY: "auto",
        border: "1px solid #e2e2e2",
        borderRadius: 3,
        padding: "10px 12px",
        boxSizing: "border-box",
        textAlign: "left",
    },
    logEntry: {
        margin: "0 0 6px",
        fontSize: 14,
        color: "#666666",
    },
    logPlayer: {
        fontWeight: 700,
    },
    logSuccess: {
        color: "#2e8b57",
    },
    logError: {
        color: "#c0392b",
    },
};
