export type PlayerId = string;
export type RoundId = string;
export type LobbyId = string;

export interface Coordinates {
  lat: number;
  lng: number;
}

export interface Player {
  id: PlayerId;
  name: string;
  joinedAt: string;
  isHost: boolean;
  score: number;
  connected: boolean;
}

export interface Guess {
  playerId: PlayerId;
  roundId: RoundId;
  coordinates: Coordinates;
  distanceMeters: number | null;
  pointsAwarded: number | null;
  submittedAt: string;
}

export interface RoundLocation {
  imageId: string;
  coordinates: Coordinates;
  capturedAt?: string;
  city?: string;
}

export type GamePhase = "lobby" | "countdown" | "guessing" | "scoring" | "finished";

export interface LeaderboardEntry {
  playerId: PlayerId;
  score: number;
  rank: number;
}

export interface GameState {
  lobbyId: LobbyId;
  hostPlayerId: PlayerId;
  phase: GamePhase;
  roundNumber: number;
  maxRounds: number;
  roundDurationMs: number;
  currentRoundId: RoundId | null;
  currentLocation: RoundLocation | null;
  players: Player[];
  guesses: Guess[];
  leaderboard: LeaderboardEntry[];
  roundStartedAt: string | null;
}

export interface SessionLeaderboard {
  lobbyId: LobbyId;
  entries: LeaderboardEntry[];
  updatedAt: string;
}

export interface JoinLobbyPayload {
  lobbyId: LobbyId;
  playerName: string;
}

export interface StartRoundPayload {
  lobbyId: LobbyId;
}

export interface SubmitGuessPayload {
  lobbyId: LobbyId;
  roundId: RoundId;
  coordinates: Coordinates;
}

