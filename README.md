# Connect 4 — Minimax Engine

A Connect 4 engine written in C++, using minimax search with alpha-beta pruning on a bitboard, plus a Python/Tkinter interface to play against it and to benchmark it: against another build, against itself at different depths, or against the AI on [ludolab.net](https://ludolab.net/play/four-in-a-line/computer).

> The project is a work in progress — the evaluation function in particular still has room for improvement.

## Features

- **Engine (C++)**
  - Board stored as two 64-bit bitboards (`pos` / `mask`), 7 columns × 6 rows.
  - Minimax with alpha-beta pruning and center-first move ordering (`3, 2, 4, 1, 5, 0, 6`).
  - Configurable search depth.
  - Heuristic evaluation: central column control plus scoring of every 4-cell window (vertical, horizontal and both diagonals) by how many pieces each side has in it.
  - Talks to the outside world through a simple text protocol over stdin/stdout.
- **Interface (Python)**
  - Local GUI to play against the engine, choosing depth and who starts.
  - `--self-play`: two engine builds play each other, alternating who starts.
  - `--depth-duel`: the same build plays itself at two different depths.
  - `--ludolab`: the engine plays the ludolab.net AI through a headless browser (Playwright).
  - `--watch`: live board window for any of the automatic modes.
  - Every game is saved to `games/*.jsonl` and can be listed or replayed; a results chart is generated after each run.

## Project structure

```
Board.cpp / Board.h     bitboard moves, column height, win/tie detection
MinMax.cpp / MinMax.h   minimax search with alpha-beta pruning and eval function
main.cpp                engine entry point (stdin/stdout protocol)
Interface.py            Tkinter GUI and automatic match modes
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

### Engine vs. engine (two builds)

```bash
python Interface.py --self-play --engine-a output/mIniMax.exe --engine-b output/mIniMax_alfaBetaPruning.exe --depth 6 --games 10 --watch
```

### Same engine, different depths

```bash
python Interface.py --depth-duel --depth-a 5 --depth-b 8 --games 20 --watch
```

### Engine vs. ludolab.net AI

```bash
python Interface.py --ludolab --depth 8 --ai-level 5 --games 10 --watch
```

### Saved games

```bash
python Interface.py --list-games              # ludolab games
python Interface.py --list-selfplay-games
python Interface.py --list-depthduel-games
python Interface.py --replay 3                # replay ludolab game #3
```

Run `python Interface.py --help` for all options (`--side`, `--show-browser`, `--engine-timeout`, `--replay-delay`, …).

## Engine protocol

One command per line on stdin; the engine replies on stdout.

| Direction | Command | Meaning |
|---|---|---|
| in  | `depth <n>`  | set search depth (≥ 1) |
| in  | `new <0\|1>` | start a new game — `1`: opponent moves first, `0`: engine moves first |
| in  | `play <col>` | opponent played in column `col` (0–6) |
| in  | `quit`       | exit |
| out | `move <col>` | column chosen by the engine |
| out | `eval <n>`   | static evaluation of the current position |

This makes it easy to plug the engine into other front-ends or test harnesses.

## Next steps

- Improve the evaluation function (threat detection, odd/even row parity).
- Add a transposition table and iterative deepening.
- Time-based search instead of fixed depth.
