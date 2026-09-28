# Connect 4 — Minimax Engine

A Connect 4 engine written in C++, using minimax search with alpha-beta pruning on a bitboard, plus a Python/Tkinter interface to play against it and to benchmark it: against another build, against itself at different depths or time limits, against the AI on [ludolab.net](https://ludolab.net/play/four-in-a-line/computer), and against rated bots to estimate its Elo.

> The project is a work in progress — the evaluation function in particular still has room for improvement.

## Features

- **Engine (C++)**
  - Board stored as two 64-bit bitboards (`pos` / `mask`), 7 columns × 6 rows.
  - Minimax with alpha-beta pruning and center-first move ordering (`3, 2, 4, 1, 5, 0, 6`).
  - Iterative deepening, searching by fixed depth or by a time limit per move; stops early when a forced win or loss is found.
  - Transposition table of fixed size (2²² entries, ~96 MB): stores value, depth, best move and bound type (exact / upper / lower); the stored best move is tried first on the next visit.
  - Win/loss scores are measured in plies from the root, so the engine prefers faster wins and slower losses.
  - Heuristic evaluation: central column control plus scoring of every 4-cell window (vertical, horizontal and both diagonals), counted with bitmasks and `popcount`.
  - Talks to the outside world through a simple text protocol over stdin/stdout.
- **Interface (Python)**
  - Local GUI to play against the engine, choosing depth and who starts.
  - `--self-play`: two engine builds (or the same build with different settings) play each other, alternating who starts.
  - `--depth-duel`: the same build plays itself at two different depths.
  - `--ludolab`: the engine plays the ludolab.net AI through a headless browser (Playwright).
  - `--time` / `--time-a` / `--time-b`: time limit per move instead of fixed depth.
  - `--watch`: live board window for any of the automatic modes.
  - Every game is saved to `games/*.jsonl` and can be listed or replayed; a results chart is generated after each run.
- **Elo measurement** (`elo_c4env.py`): rates the engine against the reference bots of [Connect-4-env](https://github.com/lucasBertola/Connect-4-env).

## Project structure

```
Board.cpp / Board.h     bitboard moves, column height, win/tie detection
MinMax.cpp / MinMax.h   search (alpha-beta, iterative deepening, transposition table) and eval
main.cpp                engine entry point (stdin/stdout protocol)
Interface.py            Tkinter GUI and automatic match modes
elo_c4env.py            Elo measurement against the Connect-4-env bots
output/                 compiled engine builds
games/                  saved games (.jsonl) and result charts (.png)
```

## Building the engine

Requires g++ (on Windows, MSYS2/MinGW).

```bash
# Linux / macOS
g++ -O2 -mpopcnt -o output/mIniMax main.cpp Board.cpp MinMax.cpp

# Windows (MSYS2 / MinGW)
g++ -O2 -mpopcnt -o output/mIniMax.exe main.cpp Board.cpp MinMax.cpp
```

`-mpopcnt` matters: the evaluation counts pieces with `__builtin_popcountll`, and without this flag g++ replaces it with a slower software routine — the search runs about 1.6× slower. Any x86-64 CPU from the last ~15 years supports it. `-march=native` also works, but the resulting binary may not run on other machines.

The interface looks for `output/mIniMax.exe` or `output/mIniMax` by default. Any other build can be passed with `--engine`, `--engine-a` or `--engine-b`.

### What `--depth` means

`--depth n` makes the engine look **n moves ahead** (plies, counting both players). Builds before the transposition-table rework (commit `356077e`) looked `n + 1` moves ahead for the same number, so when comparing against old results or old executables, add 1 to the old depth.

With `--time`, the depth is not fixed: iterative deepening goes as deep as the time limit allows.

## Running the interface

Requires Python 3 with Tkinter (on Debian/Ubuntu: `sudo apt install python3-tk`). Result charts use `matplotlib`, and the ludolab mode uses `playwright`:

```bash
pip install matplotlib playwright
python -m playwright install chromium
```

### Play against the engine

```bash
python Interface.py
```

### Engine vs. engine

```bash
# two builds, same depth
python Interface.py --self-play --watch --engine-a output/buildA --engine-b output/buildB --depth 10 --games 10

# same build, time limit vs. fixed depth
python Interface.py --self-play --watch --engine-a output/mIniMax --engine-b output/mIniMax --time-a 1000 --depth-b 12 --games 10
```

The engine is deterministic at fixed depth, so self-play with the same settings repeats the same two games (one per starting side). For a reliable strength comparison use many games from varied openings.

### Same engine, different depths

```bash
python Interface.py --depth-duel --watch --depth-a 6 --depth-b 10 --games 20
```

### Engine vs. ludolab.net AI

```bash
python Interface.py --ludolab --watch --ai-level 7 --time 2000 --games 10
```

### Saved games

```bash
python Interface.py --list-games              # ludolab games
python Interface.py --list-selfplay-games
python Interface.py --list-depthduel-games
python Interface.py --replay 3                # replay ludolab game #3
```

Run `python Interface.py --help` for all options (`--side`, `--show-browser`, `--engine-timeout`, `--replay-delay`, …).

## Measuring Elo

`elo_c4env.py` plays the engine against the reference bots of [Connect-4-env](https://github.com/lucasBertola/Connect-4-env): 8 rule-based bots (Elo 1000 to 1776) and 7 neural networks trained by self-play (`SelfTrained1`–`7`, Elo 1391 to 2573).

The scale is internal to that package (a random player is 1000), so the number only compares the engine with those bots — it is not comparable to chess Elo or to other sites.

Install the dependencies (CPU-only PyTorch is enough):

```bash
pip install --user torch --index-url https://download.pytorch.org/whl/cpu
pip install --user git+https://github.com/lucasBertola/Connect-4-env
```

Two modes:

```bash
# package's own leaderboard: plays the 2 bots closest to the current estimate and adjusts
python elo_c4env.py --engine output/mIniMax --time 100 --matches 100

# same, showing each game in a window
python elo_c4env.py --engine output/mIniMax --time 1000 --matches 50 --watch

# direct duel against the two strongest bots (SelfTrained6 and SelfTrained7), in parallel
python elo_c4env.py --engine output/mIniMax --time 1000 --duel 100 --workers 8
```

The duel mode is the most reliable for a strong engine: the leaderboard mode starts at 1400 and climbs slowly, so with few rounds it may never reach the strongest bots. The engine talks to the environment through the `board` protocol command (a full position, since the environment does not send move history).

### Results

Duel mode at 100 ms per move, 5 runs with different seeds (1000 games per build, 500 against each bot):

| build | vs SelfTrained6 (2410) | vs SelfTrained7 (2573) | Elo (95% interval) |
|---|---|---|---|
| `ttcentro` (hash-map transposition table) | 69.3% | 49.5% | 2561 (2540–2583) |
| `ttfixa` (fixed-size table, ply-based mate scores) | 65.8% | 49.7% | 2549 (2528–2570) |

The two builds are statistically tied, as expected: they choose the same moves at the same depth, and the fixed-size table only makes the search ~12% faster and keeps memory constant. A single run of 200 games varied by up to ±100 Elo between seeds, so repeat runs before comparing builds. Around 2550–2600 the engine is at the top of this scale, level with the strongest bot.

Run parallel duels with care at longer time limits: with 8 workers and 1 s per move (16 processes on 12 cores), the results dropped by ~250 Elo compared with 2 workers.

## Engine protocol

One command per line on stdin; the engine replies on stdout.

| Direction | Command | Meaning |
|---|---|---|
| in  | `depth <n>`  | set search depth, in moves ahead (≥ 1) |
| in  | `time <ms>`  | time limit per move in milliseconds; `0` = use `depth` |
| in  | `new <0\|1>` | start a new game — `1`: opponent moves first, `0`: engine moves first |
| in  | `play <col>` | opponent played in column `col` (0–6) |
| in  | `board <42 cells>` | search a standalone position: rows top to bottom, `0` empty, `1` engine (side to move), `2` opponent; does not change the game tracked by `new`/`play` |
| in  | `quit`       | exit |
| out | `move <col>` | column chosen by the engine |
| out | `eval <n>`   | static evaluation of the current position |

This makes it easy to plug the engine into other front-ends or test harnesses.

## Next steps

- Improve the evaluation function (threat detection, odd/even row parity, one count per threat square instead of per window).
- Evaluate all windows of a direction at once with bitboard shifts (measured about 2× faster than the current per-window masks).
- Smarter replacement policy for the transposition table (keep the deeper entry on collisions).
- Time management with a total budget per game, spending more time in the opening.
