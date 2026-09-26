"""
Interface grafica do Connect4 (tkinter), que conversa com o motor em C++
(mIniMax.cpp) por stdin/stdout usando o seguinte protocolo, um comando por
linha:

  Python -> C++
    depth <n>       define a profundidade de busca (>=1)
    new <0|1>       comeca um novo jogo. 1 = humano comeca, 0 = computador comeca
    play <col>      humano jogou na coluna <col> (0 a 6)
    quit            encerra o motor

  C++ -> Python
    move <col>      coluna escolhida pelo motor (enviada apos "new 0" e apos
                     cada "play <col>")

Veja o final deste arquivo / a mensagem que acompanha esta mudanca para saber
exatamente o que precisa ser alterado em mIniMax.cpp para implementar esse
protocolo.
"""

import argparse
import json
import os
import queue
import subprocess
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

COLS = 7
ROWS = 6
CELL = 90
PAD = 12
RADIUS = CELL // 2 - 8

COLOR_BG = "#0d1b2a"
COLOR_BOARD = "#1565c0"
COLOR_EMPTY = "#e8eef5"
COLOR_HUMAN = "#e53935"   # vermelho
COLOR_BOT = "#fdd835"     # amarelo
COLOR_HOVER = "#1976d2"

HUMAN = "human"
BOT = "bot"


def _resolve_engine_path(explicit_path, names):
    """Resolve o caminho de um executavel do motor.

    Se explicit_path for dado, exige que ele exista. Senao, procura por
    qualquer nome em `names` dentro de output/ e da pasta do script."""
    if explicit_path:
        if os.path.isfile(explicit_path):
            return explicit_path
        raise FileNotFoundError(f"Executavel do motor nao encontrado: {explicit_path}")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for name in names:
        for candidate in (os.path.join(base_dir, "output", name), os.path.join(base_dir, name)):
            if os.path.isfile(candidate):
                return candidate
    return None


def find_engine_path():
    return _resolve_engine_path(None, ["mIniMax.exe", "mIniMax"])


def find_engine_b_path():
    """Segundo build do motor, usado no modo --self-play (motor A vs motor B).
    Por convencao, o build "novo"/em teste fica em output/mIniMax-novo.exe."""
    return _resolve_engine_path(None, ["mIniMax-novo.exe", "mIniMax-novo", "mIniMax_novo.exe"])


class Engine:
    """Mantem o processo do motor C++ vivo e le as respostas em uma thread
    separada, entregando as jogadas do bot por meio de uma fila."""

    def __init__(self, exe_path):
        self.process = subprocess.Popen(
            [exe_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.moves = queue.Queue()
        # O motor emite duas avaliacoes por "play": a primeira logo apos aplicar
        # o lance do adversario (antes de pensar) e a segunda apos o proprio
        # lance dele. A fila preserva essa ordem; last_eval guarda so a ultima.
        self.evals = queue.Queue()
        self.last_eval = None
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self):
        for linha in self.process.stdout:
            linha = linha.strip()
            if linha.startswith("move"):
                partes = linha.split()
                if len(partes) == 2 and partes[1].isdigit():
                    self.moves.put(int(partes[1]))
            elif linha.startswith("eval"):
                partes = linha.split()
                if len(partes) == 2:
                    try:
                        valor = int(partes[1])
                    except ValueError:
                        continue
                    self.last_eval = valor
                    self.evals.put(valor)

    def send(self, comando):
        if self.process.poll() is not None:
            raise RuntimeError("O motor C++ nao esta mais em execucao.")
        self.process.stdin.write(comando + "\n")
        self.process.stdin.flush()

    def set_depth(self, depth):
        self.send(f"depth {depth}")

    def set_time(self, ms):
        """Limite de tempo por lance, em milissegundos. Quando > 0 o motor
        busca por tempo (iterative deepening) e ignora a profundidade."""
        self.send(f"time {ms}")

    def new_game(self, human_starts):
        self.send(f"new {1 if human_starts else 0}")

    def play(self, col):
        self.send(f"play {col}")

    def quit(self):
        try:
            self.send("quit")
        except Exception:
            pass
        try:
            self.process.terminate()
        except Exception:
            pass


# Segundos de espera por uma linha "eval". O motor a imprime junto com o lance
# (nao depende da busca), entao um tempo curto basta -- e evita travar a partida
# inteira caso a fila saia de sincronia por algum motivo.
EVAL_TIMEOUT = 10


def _read_engine_eval(engine, timeout=EVAL_TIMEOUT):
    """Consome a proxima avaliacao emitida pelo motor, na ordem em que saiu.
    Devolve None se ela nao chegar a tempo (preferimos mostrar '--' a derrubar
    a partida)."""
    try:
        return engine.evals.get(timeout=timeout)
    except queue.Empty:
        return None


class SetupDialog(tk.Toplevel):
    """Janela modal para escolher profundidade de busca e quem comeca."""

    def __init__(self, master, depth_default=5, human_starts_default=True):
        super().__init__(master)
        self.title("Novo jogo")
        self.resizable(False, False)
        self.configure(bg=COLOR_BG, padx=20, pady=16)
        self.result = None

        tk.Label(self, text="Profundidade de busca do bot:",
                 bg=COLOR_BG, fg="white").grid(row=0, column=0, columnspan=2, sticky="w")

        self.depth_var = tk.IntVar(value=depth_default)
        depth_spin = tk.Spinbox(self, from_=1, to=12, width=5, textvariable=self.depth_var)
        depth_spin.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 14))

        tk.Label(self, text="Quem comeca?", bg=COLOR_BG, fg="white").grid(
            row=2, column=0, columnspan=2, sticky="w")

        self.starter_var = tk.StringVar(value="human" if human_starts_default else "bot")
        tk.Radiobutton(self, text="Eu (vermelho)", variable=self.starter_var, value="human",
                        bg=COLOR_BG, fg="white", selectcolor="#1b2a3a",
                        activebackground=COLOR_BG, activeforeground="white"
                        ).grid(row=3, column=0, sticky="w")
        tk.Radiobutton(self, text="Computador (amarelo)", variable=self.starter_var, value="bot",
                        bg=COLOR_BG, fg="white", selectcolor="#1b2a3a",
                        activebackground=COLOR_BG, activeforeground="white"
                        ).grid(row=4, column=0, sticky="w", pady=(0, 14))

        btn = tk.Button(self, text="Comecar", command=self._confirm, bg=COLOR_BOARD,
                         fg="white", relief="flat", padx=10, pady=4)
        btn.grid(row=5, column=0, columnspan=2, pady=(4, 0))

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.transient(master)
        self.grab_set()

    def _confirm(self):
        self.result = (int(self.depth_var.get()), self.starter_var.get() == "human")
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class Connect4GUI:
    def __init__(self, root, exe_path):
        self.root = root
        self.root.title("Connect 4")
        self.root.configure(bg=COLOR_BG)
        self.root.resizable(False, False)

        self.exe_path = exe_path
        self.engine = None

        width = COLS * CELL + 2 * PAD
        board_height = ROWS * CELL + 2 * PAD

        self.status_var = tk.StringVar(value="Bem-vindo ao Connect 4!")
        tk.Label(root, textvariable=self.status_var, bg=COLOR_BG, fg="white",
                 font=("Segoe UI", 13, "bold"), pady=10).pack(fill="x")

        self.canvas = tk.Canvas(root, width=width, height=board_height,
                                 bg=COLOR_BG, highlightthickness=0)
        self.canvas.pack()

        self.eval_var = tk.StringVar(value="Avaliacao: --")
        tk.Label(root, textvariable=self.eval_var, bg=COLOR_BG, fg="#9fb3c8",
                 font=("Consolas", 11), pady=6).pack(fill="x")

        controls = tk.Frame(root, bg=COLOR_BG)
        controls.pack(pady=10)
        tk.Button(controls, text="Novo jogo", command=self.start_new_game,
                  bg=COLOR_BOARD, fg="white", relief="flat", padx=14, pady=6
                  ).pack(side="left", padx=6)
        tk.Button(controls, text="Sair", command=self.on_close,
                  bg="#455a64", fg="white", relief="flat", padx=14, pady=6
                  ).pack(side="left", padx=6)

        self.canvas.bind("<Motion>", self.on_hover)
        self.canvas.bind("<Leave>", lambda e: self.redraw())
        self.canvas.bind("<Button-1>", self.on_click)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.board = None
        self.game_over = True
        self.human_turn = False
        self.hover_col = None
        self.depth = 5
        self.human_starts_default = True

        self.draw_empty_board()
        self.root.after(200, self.start_new_game)
        self.root.after(50, self.poll_bot_move)

    # ---------------------------------------------------------------- board

    def draw_empty_board(self):
        self.canvas.delete("all")
        width = COLS * CELL + 2 * PAD
        height = ROWS * CELL + 2 * PAD
        self.canvas.create_rectangle(0, 0, width, height, fill=COLOR_BOARD, outline="")
        for col in range(COLS):
            for row in range(ROWS):
                self._draw_disc(col, row, COLOR_EMPTY)

    def _cell_center(self, col, row):
        x = PAD + col * CELL + CELL // 2
        y = PAD + (ROWS - 1 - row) * CELL + CELL // 2
        return x, y

    def _draw_disc(self, col, row, color):
        x, y = self._cell_center(col, row)
        self.canvas.create_oval(x - RADIUS, y - RADIUS, x + RADIUS, y + RADIUS,
                                 fill=color, outline="")

    def redraw(self):
        self.canvas.delete("all")
        width = COLS * CELL + 2 * PAD
        height = ROWS * CELL + 2 * PAD
        self.canvas.create_rectangle(0, 0, width, height, fill=COLOR_BOARD, outline="")

        if self.hover_col is not None and self.human_turn and not self.game_over:
            x0 = PAD + self.hover_col * CELL
            self.canvas.create_rectangle(x0, 0, x0 + CELL, height, fill=COLOR_HOVER, outline="")

        for col in range(COLS):
            for row in range(ROWS):
                cell = self.board[col][row] if self.board else "*"
                if cell == "x":
                    color = COLOR_BOT
                elif cell == "o":
                    color = COLOR_HUMAN
                else:
                    color = COLOR_EMPTY
                self._draw_disc(col, row, color)

    # ------------------------------------------------------------- gameplay

    def start_new_game(self):
        if self.engine is None:
            if not self.exe_path:
                messagebox.showerror(
                    "Motor nao encontrado",
                    "Nao encontrei o executavel do motor (mIniMax.exe).\n\n"
                    "Compile mIniMax.cpp, por exemplo:\n"
                    "  g++ -O2 -o output/mIniMax.exe mIniMax.cpp\n\n"
                    "e coloque o arquivo gerado em output/mIniMax.exe ou na "
                    "mesma pasta deste script."
                )
                self.root.destroy()
                return
            try:
                self.engine = Engine(self.exe_path)
            except Exception as exc:
                messagebox.showerror("Erro ao iniciar o motor", str(exc))
                self.root.destroy()
                return

        dialog = SetupDialog(self.root, self.depth, self.human_starts_default)
        self.root.wait_window(dialog)
        if dialog.result is None:
            return

        self.depth, human_starts = dialog.result
        self.human_starts_default = human_starts

        self.board = [["*"] * ROWS for _ in range(COLS)]
        self.game_over = False
        self.hover_col = None
        self.engine.last_eval = None
        self.eval_var.set("Avaliacao: --")

        try:
            self.engine.set_depth(self.depth)
            self.engine.new_game(human_starts)
        except Exception as exc:
            messagebox.showerror("Erro de comunicacao com o motor", str(exc))
            return

        self.human_turn = human_starts
        self.status_var.set("Sua vez (vermelho)" if human_starts else "Computador pensando...")
        self.redraw()

    def lowest_empty_row(self, col):
        for row in range(ROWS):
            if self.board[col][row] == "*":
                return row
        return None

    def drop_piece(self, col, symbol):
        row = self.lowest_empty_row(col)
        if row is None:
            return None
        self.board[col][row] = symbol
        return row

    def check_winner(self, col, row):
        symbol = self.board[col][row]
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        for dc, dr in directions:
            count = 1
            c, r = col + dc, row + dr
            while 0 <= c < COLS and 0 <= r < ROWS and self.board[c][r] == symbol:
                count += 1
                c += dc
                r += dr
            c, r = col - dc, row - dr
            while 0 <= c < COLS and 0 <= r < ROWS and self.board[c][r] == symbol:
                count += 1
                c -= dc
                r -= dr
            if count >= 4:
                return True
        return False

    def board_full(self):
        return all(self.board[c][ROWS - 1] != "*" for c in range(COLS))

    def on_hover(self, event):
        if not self.human_turn or self.game_over or self.board is None:
            return
        col = (event.x - PAD) // CELL
        col = max(0, min(COLS - 1, col))
        if col != self.hover_col:
            self.hover_col = col
            self.redraw()

    def on_click(self, event):
        if self.game_over or not self.human_turn or self.board is None:
            return
        col = (event.x - PAD) // CELL
        if not (0 <= col < COLS):
            return
        if self.lowest_empty_row(col) is None:
            return

        row = self.drop_piece(col, "o")
        self.redraw()

        if self.check_winner(col, row):
            self.finish_game("Voce venceu! Parabens.")
            return
        if self.board_full():
            self.finish_game("Empate!")
            return

        self.human_turn = False
        self.status_var.set("Computador pensando...")
        try:
            self.engine.play(col)
        except Exception as exc:
            messagebox.showerror("Erro de comunicacao com o motor", str(exc))

    def poll_bot_move(self):
        if self.engine is not None:
            if self.engine.last_eval is not None:
                self.eval_var.set(f"Avaliacao: {self.engine.last_eval}")
            if not self.game_over:
                try:
                    col = self.engine.moves.get_nowait()
                except queue.Empty:
                    col = None
                if col is not None:
                    self.apply_bot_move(col)
        self.root.after(50, self.poll_bot_move)

    def apply_bot_move(self, col):
        row = self.drop_piece(col, "x")
        if row is None:
            return
        self.redraw()

        if self.check_winner(col, row):
            self.finish_game("O computador venceu. Tente novamente!")
            return
        if self.board_full():
            self.finish_game("Empate!")
            return

        self.human_turn = True
        self.status_var.set("Sua vez (vermelho)")

    def finish_game(self, mensagem):
        self.game_over = True
        self.human_turn = False
        self.status_var.set(mensagem)

    def on_close(self):
        if self.engine is not None:
            self.engine.quit()
        self.root.destroy()


# ---------------------------------------------------------------------------
# Modo automatico: nosso motor C++ joga sozinho contra a IA do site
# https://ludolab.net/play/four-in-a-line/computer, sem nenhuma interacao
# manual (mouse/teclado). Usa Playwright para abrir um navegador de verdade,
# ler o tabuleiro pelo DOM e clicar nas colunas.
#
# So funciona com um interprete Python que tenha o pacote "playwright"
# instalado (com "python -m playwright install chromium"). Veja a mensagem
# de erro exibida se o pacote nao estiver disponivel.
# ---------------------------------------------------------------------------

LUDOLAB_URL = "https://ludolab.net/play/four-in-a-line/computer"

GAMES_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "games", "ludolab_games.jsonl")

SELFPLAY_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "games", "selfplay_games.jsonl")

# --depth-duel guarda em arquivo separado: e outro experimento (mesmo binario,
# profundidades diferentes) e misturar com o --self-play tornaria os dois
# conjuntos de dados incomparaveis.
DEPTHDUEL_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "games", "depthduel_games.jsonl")


def _append_record(path, record):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _load_records(path):
    """Le todas as partidas salvas no arquivo, mais antiga primeiro."""
    if not os.path.isfile(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _save_game_record(record):
    _append_record(GAMES_LOG_PATH, record)


def load_game_records():
    return _load_records(GAMES_LOG_PATH)


def load_selfplay_records():
    return _load_records(SELFPLAY_LOG_PATH)


def load_depthduel_records():
    return _load_records(DEPTHDUEL_LOG_PATH)


# --------------------------------------------------------------------- board
# Rastreamento de tabuleiro independente do motor/site, usado pelo modo
# --self-play (dois motores locais nao tem um site externo para avisar quando
# o jogo termina, entao verificamos vitoria/empate por conta propria).

def _new_local_board():
    return [["*"] * ROWS for _ in range(COLS)]


def _drop_on_board(board, col, symbol):
    for r in range(ROWS):
        if board[col][r] == "*":
            board[col][r] = symbol
            return r
    return None


def _check_winner_on_board(board, col, row):
    symbol = board[col][row]
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    for dc, dr in directions:
        count = 1
        c, r = col + dc, row + dr
        while 0 <= c < COLS and 0 <= r < ROWS and board[c][r] == symbol:
            count += 1
            c += dc
            r += dr
        c, r = col - dc, row - dr
        while 0 <= c < COLS and 0 <= r < ROWS and board[c][r] == symbol:
            count += 1
            c -= dc
            r -= dr
        if count >= 4:
            return True
    return False


def _board_full_check(board):
    return all(board[c][ROWS - 1] != "*" for c in range(COLS))


# --------------------------------------------------------------------- chart
# Graficos de resultado (vitorias/derrotas/empates, separados por quem jogou
# primeiro), gerados ao final de cada rodada de --ludolab ou --self-play.

def _bar_chart_grouped(groups, series, series_colors, title, ylabel, save_path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        raise RuntimeError(
            "O pacote 'matplotlib' nao esta disponivel neste interprete "
            "Python.\nInstale com: pip install matplotlib"
        )

    n_groups = len(groups)
    n_series = len(series)
    width = 0.8 / max(n_series, 1)
    x = list(range(n_groups))

    fig, ax = plt.subplots(figsize=(1.8 * n_groups + 2, 5))
    for i, (name, counts) in enumerate(series.items()):
        offset = (i - (n_series - 1) / 2) * width
        xs = [xi + offset for xi in x]
        bars = ax.bar(xs, counts, width, label=name, color=series_colors.get(name))
        ax.bar_label(bars, padding=2)

    ax.set_xticks(x)
    ax.set_xticklabels(groups)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    ax.margins(y=0.15)
    fig.tight_layout()

    out_dir = os.path.dirname(save_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    return save_path


def plot_ludolab_results(records, save_path):
    groups = ["Jogando primeiro", "Jogando segundo"]
    counts = {"Vitorias": [0, 0], "Derrotas": [0, 0], "Empates": [0, 0]}
    for r in records:
        idx = 0 if r.get("our_side") == "player1" else 1
        res = r.get("result")
        if res == "ours":
            counts["Vitorias"][idx] += 1
        elif res == "ludolab":
            counts["Derrotas"][idx] += 1
        elif res == "empate":
            counts["Empates"][idx] += 1
    colors = {"Vitorias": "#43a047", "Derrotas": "#e53935", "Empates": "#9e9e9e"}
    return _bar_chart_grouped(groups, counts, colors,
                               "Nosso motor vs ludolab AI", "Partidas", save_path)


def _tally_two_sided(records):
    """Conta vitorias/derrotas/empates dos dois lados de um confronto local,
    separando por quem comecou. Indices dos grupos:
      0 = A comecou, 1 = A jogou por ultimo (B comecou),
      2 = B comecou, 3 = B jogou por ultimo (A comecou)"""
    counts = {"Vitorias": [0] * 4, "Derrotas": [0] * 4, "Empates": [0] * 4}
    for r in records:
        starter = r.get("starter")
        res = r.get("result")
        idx_a, idx_b = (0, 3) if starter == "a" else (1, 2)
        if res == "a":
            counts["Vitorias"][idx_a] += 1
            counts["Derrotas"][idx_b] += 1
        elif res == "b":
            counts["Vitorias"][idx_b] += 1
            counts["Derrotas"][idx_a] += 1
        elif res == "empate":
            counts["Empates"][idx_a] += 1
            counts["Empates"][idx_b] += 1
    return counts


_RESULT_COLORS = {"Vitorias": "#43a047", "Derrotas": "#e53935", "Empates": "#9e9e9e"}


def plot_selfplay_results(records, save_path):
    groups = ["Motor A - 1o", "Motor A - 2o", "Motor B - 1o", "Motor B - 2o"]
    return _bar_chart_grouped(groups, _tally_two_sided(records), _RESULT_COLORS,
                               "Motor A vs Motor B (autoconfronto)", "Partidas", save_path)


def plot_depthduel_results(records, save_path, depth_a, depth_b):
    """Grafico do --depth-duel. Considera apenas as partidas com esse mesmo par
    de profundidades -- misturar pares diferentes compararia experimentos que
    nao sao comparaveis entre si."""
    do_par = [r for r in records
              if r.get("depth_a") == depth_a and r.get("depth_b") == depth_b]
    groups = [f"Prof. {depth_a} - 1o", f"Prof. {depth_a} - 2o",
              f"Prof. {depth_b} - 1o", f"Prof. {depth_b} - 2o"]
    return _bar_chart_grouped(
        groups, _tally_two_sided(do_par), _RESULT_COLORS,
        f"Mesmo binario: profundidade {depth_a} vs {depth_b}", "Partidas", save_path)


def _ludolab_read_state(page):
    """Le o tabuleiro renderizado pelo site.

    Retorna (columns, mover, game_over):
      columns: lista de 7 listas (uma por coluna), cada uma com "player1"/
               "player2" na ordem em que as pecas foram empilhadas de baixo
               para cima.
      mover: "player1" ou "player2" -- de quem e a vez agora (pode ser None
             durante uma animacao/pensamento, mesmo com o jogo em andamento).
      game_over: True quando o site marca uma vitoria (classe "victory") ou
                 quando o tabuleiro esta cheio (empate). Nao usamos apenas a
                 ausencia de uma casa "playable" porque ela some por um
                 instante durante a animacao de queda da peca e durante o
                 tempo de calculo da IA.
    """
    cols = page.query_selector_all(".c4-board > .column")
    columns = []
    mover = None
    has_victory = False
    for col in cols:
        pieces = []
        for cell in col.query_selector_all(".cell"):
            cls = cell.get_attribute("class") or ""
            if "victory" in cls:
                has_victory = True
            if "playable" in cls:
                mover = "player1" if "player1" in cls else "player2"
            if "token" in cls:
                pieces.append("player1" if "player1" in cls else "player2")
        columns.append(pieces)
    total_pieces = sum(len(c) for c in columns)
    game_over = has_victory or total_pieces == COLS * ROWS
    return columns, mover, game_over


def _ludolab_configure(page, ai_level, our_side):
    page.goto(LUDOLAB_URL, wait_until="networkidle")
    page.wait_for_timeout(500)
    page.get_by_role("button", name=str(ai_level), exact=True).click()
    side_class = "player1" if our_side == "player1" else "player2"
    page.query_selector(f"button.{side_class}.secondary.square").click()
    page.get_by_role("button", name="Play", exact=True).click()
    page.wait_for_timeout(500)


def _ludolab_click_column(page, col):
    page.query_selector_all(".c4-board > .column")[col].click()
    page.wait_for_timeout(250)


def _ludolab_wait_for_move(page, known_counts, poll=0.2, timeout=60):
    """Espera ate que uma coluna ganhe uma peca nova (retorna seu indice) ou
    o jogo termine (retorna None). known_counts e a contagem de pecas por
    coluna vista antes dessa espera."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        page.wait_for_timeout(int(poll * 1000))
        columns, _mover, over = _ludolab_read_state(page)
        counts = [len(c) for c in columns]
        for i, (before, now) in enumerate(zip(known_counts, counts)):
            if now > before:
                return i, columns
        if over:
            return None, columns
    raise TimeoutError("O adversario em ludolab.net demorou demais para jogar.")


def _flip_side(side):
    return "player2" if side == "player1" else "player1"


def run_ludolab_match(exe_path, depth=8, ai_level=5, our_side="player1",
                       headless=True, games=1, on_event=None, engine_timeout=180):
    """on_event, se fornecido, e chamado com tuplas:
      ("new_game", numero_da_partida)
      ("move", coluna, "ours" | "ludolab")
      ("game_end", "ours" | "ludolab" | "empate")
      ("final", placar_dict)
      ("error", mensagem)
    Usado pela janela de visualizacao (--watch); no modo so-console isso
    fica None e o progresso e so impresso no terminal.

    our_side define o lado da primeira partida; a partir dai o lado alterna
    a cada partida, entao (com games par) metade das partidas comeca com
    nosso motor jogando primeiro e a outra metade jogando segundo.
    """
    def emit(*event):
        if on_event:
            on_event(event)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        msg = (
            "O pacote 'playwright' nao esta disponivel neste interprete "
            "Python.\n\nInstale com:\n"
            "  pip install playwright\n"
            "  python -m playwright install chromium\n\n"
            "Se voce criou um ambiente virtual so para isso, rode este "
            "script com o python de dentro dele, por exemplo:\n"
            "  .venv\\Scripts\\python.exe Interface.py --ludolab"
        )
        print(msg)
        emit("error", msg)
        return

    placar = {"ours": 0, "ludolab": 0, "empate": 0}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        for game_no in range(1, games + 1):
            current_side = our_side if game_no % 2 == 1 else _flip_side(our_side)

            engine = Engine(exe_path)
            engine.set_depth(depth)

            def next_eval():
                # o motor sempre imprime a avaliacao do ponto de vista de
                # quem joga via "play" (o adversario, aqui o ludolab) --
                # inverte o sinal pra positivo significar "bom pro nosso bot".
                # Le da fila em vez de last_eval porque sao duas avaliacoes por
                # lance: uma logo apos o lance do ludolab e outra apos o nosso.
                valor = _read_engine_eval(engine)
                return None if valor is None else -valor

            print(f"\n=== Partida {game_no}/{games}: nosso motor (profundidade {depth}) "
                  f"como {'primeiro' if current_side == 'player1' else 'segundo'} "
                  f"vs ludolab AI Level {ai_level} ===")
            emit("new_game", game_no)

            _ludolab_configure(page, ai_level, current_side)

            we_are_first = current_side == "player1"
            engine.new_game(human_starts=not we_are_first)

            counts = [0] * COLS
            last_mover = None
            move_log = []

            def report(col, side, eval_value):
                nome = "nosso motor" if side == "ours" else "ludolab AI"
                aval = "--" if eval_value is None else eval_value
                print(f"  {nome}: coluna {col}   (avaliacao: {aval})")
                emit("move", col, side, eval_value)
                move_log.append({"col": col, "side": side})

            if we_are_first:
                col = engine.moves.get(timeout=engine_timeout)
                _ludolab_click_column(page, col)
                counts[col] += 1
                report(col, "ours", next_eval())
                last_mover = "ours"
            else:
                # o lance de abertura da IA acontece como efeito colateral
                # do clique em "Play" dentro de _ludolab_configure
                opp_col, _ = _ludolab_wait_for_move(page, counts, timeout=30)
                if opp_col is None:
                    raise RuntimeError("Esperava o primeiro lance da IA e o jogo ja terminou.")
                counts[opp_col] += 1
                last_mover = "ludolab"

                # manda o lance antes de reportar: a avaliacao pos-lance do
                # adversario so existe depois que o motor aplica esse lance
                engine.play(opp_col)
                report(opp_col, "ludolab", next_eval())

                col = engine.moves.get(timeout=engine_timeout)
                _ludolab_click_column(page, col)
                counts[col] += 1
                report(col, "ours", next_eval())
                last_mover = "ours"

            resultado = None
            while resultado is None:
                _columns, _mover, over = _ludolab_read_state(page)
                if over:
                    total = sum(len(c) for c in _columns)
                    resultado = "empate" if total == COLS * ROWS else last_mover
                    break

                opp_col, columns = _ludolab_wait_for_move(page, counts)
                if opp_col is None:
                    total = sum(len(c) for c in columns)
                    resultado = "empate" if total == COLS * ROWS else last_mover
                    break
                counts[opp_col] += 1
                last_mover = "ludolab"

                # essa jogada do adversario pode ter terminado o jogo -- so
                # pedimos e clicamos a resposta do nosso motor se ainda
                # houver jogo (senao esbarramos no modal de fim de partida)
                _columns2, _mover2, over2 = _ludolab_read_state(page)
                if over2:
                    # o motor nunca vai receber esse "play", entao nao existe
                    # avaliacao pos-lance para mostrar
                    report(opp_col, "ludolab", None)
                    total = sum(len(c) for c in _columns2)
                    resultado = "empate" if total == COLS * ROWS else last_mover
                    break

                engine.play(opp_col)
                report(opp_col, "ludolab", next_eval())

                col = engine.moves.get(timeout=engine_timeout)
                _ludolab_click_column(page, col)
                counts[col] += 1
                report(col, "ours", next_eval())
                last_mover = "ours"

            engine.quit()
            placar[resultado] += 1
            nome = {"ours": "nosso motor venceu", "ludolab": "ludolab AI venceu",
                    "empate": "empate"}[resultado]
            print(f"  Resultado: {nome}")
            emit("game_end", resultado)

            record = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "engine": exe_path,
                "depth": depth,
                "ai_level": ai_level,
                "our_side": current_side,
                "moves": move_log,
                "result": resultado,
            }
            _save_game_record(record)

    print(f"\n=== Placar final: nosso motor {placar['ours']} x "
          f"{placar['ludolab']} ludolab AI ({placar['empate']} empates) ===")
    emit("final", placar)

    chart_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "games", "ludolab_results.png")
    try:
        plot_ludolab_results(load_game_records(), chart_path)
        print(f"Grafico de resultados salvo em {chart_path}")
        emit("chart", chart_path)
    except Exception as exc:
        print(f"Nao foi possivel gerar o grafico de resultados: {exc}")
        emit("error", f"Nao foi possivel gerar o grafico: {exc}")


def _search_desc(depth, time_ms):
    """Descricao curta do modo de busca de um lado: por tempo ou profundidade."""
    return f"tempo {time_ms} ms" if time_ms else f"profundidade {depth}"


def run_engine_vs_engine_match(exe_a, exe_b, depth_a=8, depth_b=8, games=1,
                                on_event=None, engine_timeout=180,
                                label_a="motor A", label_b="motor B",
                                log_path=None, chart=None, time_a=0, time_b=0):
    """Faz dois motores locais (exe_a e exe_b, dois processos conversando por
    stdin/stdout) jogarem um contra o outro, sem site nem navegador. A partida
    1 comeca com o lado A, a 2 com o lado B, e assim por diante alternando --
    com games par, metade comeca com cada um.

    Serve aos dois experimentos: --self-play (dois builds diferentes, mesma
    profundidade) e --depth-duel (mesmo build, profundidades diferentes). O que
    muda entre eles sao os rotulos, o arquivo de log e o grafico:
      label_a/label_b: como cada lado aparece no terminal e nos eventos
      log_path: arquivo .jsonl onde cada partida e gravada
      chart: par (funcao_de_plot, caminho_do_png) gerado ao final
      time_a/time_b: limite de tempo por lance em ms; quando > 0 aquele lado
        busca por tempo em vez de profundidade (0 = so profundidade)

    on_event, se fornecido, recebe as mesmas tuplas de run_ludolab_match,
    trocando "ours"/"ludolab" por "a"/"b".
    """
    def emit(*event):
        if on_event:
            on_event(event)

    if log_path is None:
        log_path = SELFPLAY_LOG_PATH

    placar = {"a": 0, "b": 0, "empate": 0}
    nomes = {"a": label_a, "b": label_b}

    for game_no in range(1, games + 1):
        starter = "a" if game_no % 2 == 1 else "b"

        engine_a = Engine(exe_a)
        engine_b = Engine(exe_b)
        engine_a.set_depth(depth_a)
        engine_b.set_depth(depth_b)
        # so envia "time" quando usado: builds antigos nao conhecem o comando
        if time_a:
            engine_a.set_time(time_a)
        if time_b:
            engine_b.set_time(time_b)

        print(f"\n=== Partida {game_no}/{games}: {label_a} ({os.path.basename(exe_a)}, "
              f"{_search_desc(depth_a, time_a)}) vs {label_b} ({os.path.basename(exe_b)}, "
              f"{_search_desc(depth_b, time_b)}) -- comeca: {nomes[starter]} ===")
        emit("new_game", game_no)

        # o lado que comeca e avisado via "new 0" (ele mesmo calcula e emite
        # o primeiro lance); o outro lado e avisado via "new 1" (fica parado
        # esperando um "play" com o lance do adversario)
        engine_a.new_game(human_starts=(starter != "a"))
        engine_b.new_game(human_starts=(starter != "b"))

        board = _new_local_board()
        move_log = []
        resultado = None
        mover = starter

        while True:
            engine = engine_a if mover == "a" else engine_b
            col = engine.moves.get(timeout=engine_timeout)

            # cada motor imprime uma avaliacao logo apos o proprio lance, do
            # ponto de vista de quem o alimenta via "play" (ou seja, do
            # adversario dele) -- invertemos a do motor A para que o numero
            # exibido esteja sempre na perspectiva do motor A
            ev = _read_engine_eval(engine)
            if ev is not None and mover == "a":
                ev = -ev

            row = _drop_on_board(board, col, mover)
            print(f"  {nomes[mover]}: coluna {col}   "
                  f"(avaliacao p/ {label_a}: {'--' if ev is None else ev})")
            emit("move", col, mover, ev)
            move_log.append({"col": col, "side": mover})

            if row is not None and _check_winner_on_board(board, col, row):
                resultado = mover
                break
            if _board_full_check(board):
                resultado = "empate"
                break

            other = engine_b if mover == "a" else engine_a
            other.play(col)
            # o adversario responde com a avaliacao pos-lance antes de pensar;
            # consome para a fila dele nao sair de sincronia
            _read_engine_eval(other)
            mover = "b" if mover == "a" else "a"

        engine_a.quit()
        engine_b.quit()
        placar[resultado] += 1
        nome = "empate" if resultado == "empate" else f"{nomes[resultado]} venceu"
        print(f"  Resultado: {nome}")
        emit("game_end", resultado)

        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "engine_a": exe_a,
            "engine_b": exe_b,
            "depth_a": depth_a,
            "depth_b": depth_b,
            "time_a": time_a,
            "time_b": time_b,
            "starter": starter,
            "moves": move_log,
            "result": resultado,
        }
        _append_record(log_path, record)

    print(f"\n=== Placar final: {label_a} {placar['a']} x {placar['b']} {label_b} "
          f"({placar['empate']} empates) ===")
    emit("final", placar)

    if chart is None:
        chart = (plot_selfplay_results,
                 os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "games", "selfplay_results.png"))
    plot_fn, chart_path = chart
    try:
        plot_fn(_load_records(log_path), chart_path)
        print(f"Grafico de resultados salvo em {chart_path}")
        emit("chart", chart_path)
    except Exception as exc:
        print(f"Nao foi possivel gerar o grafico de resultados: {exc}")
        emit("error", f"Nao foi possivel gerar o grafico: {exc}")

    return placar


_LUDOLAB_COLOR_MAP = {"ours": COLOR_BOT, "ludolab": COLOR_HUMAN}
_SELFPLAY_COLOR_MAP = {"a": COLOR_BOT, "b": COLOR_HUMAN}


def _draw_two_color_board(canvas, board, color_map=None):
    """Desenha um tabuleiro cujas casas guardam duas chaves de lado (por
    padrao 'ours'/'ludolab') ou '*'. Usado pela janela --watch (ao vivo,
    tanto --ludolab quanto --self-play) e pelo replay (partidas ja salvas)."""
    color_map = color_map or _LUDOLAB_COLOR_MAP
    canvas.delete("all")
    width = COLS * CELL + 2 * PAD
    height = ROWS * CELL + 2 * PAD
    canvas.create_rectangle(0, 0, width, height, fill=COLOR_BOARD, outline="")
    for col in range(COLS):
        for row in range(ROWS):
            cell = board[col][row]
            color = color_map.get(cell, COLOR_EMPTY)
            x = PAD + col * CELL + CELL // 2
            y = PAD + (ROWS - 1 - row) * CELL + CELL // 2
            canvas.create_oval(x - RADIUS, y - RADIUS, x + RADIUS, y + RADIUS,
                                fill=color, outline="")


class LudolabWatchGUI:
    """Janela tkinter que mostra, em tempo real, a partida automatica do
    nosso motor contra a IA de ludolab.net (run_ludolab_match rodando numa
    thread separada, sem nenhuma interacao manual)."""

    def __init__(self, root, exe_path, depth, ai_level, our_side, games, engine_timeout=180):
        self.root = root
        self.root.title("Connect 4 - nosso motor vs ludolab.net")
        self.root.configure(bg=COLOR_BG)
        self.root.resizable(False, False)

        width = COLS * CELL + 2 * PAD
        height = ROWS * CELL + 2 * PAD

        self.status_var = tk.StringVar(value="Iniciando...")
        tk.Label(root, textvariable=self.status_var, bg=COLOR_BG, fg="white",
                 font=("Segoe UI", 13, "bold"), pady=10).pack(fill="x")

        self.canvas = tk.Canvas(root, width=width, height=height,
                                 bg=COLOR_BG, highlightthickness=0)
        self.canvas.pack()

        self.eval_var = tk.StringVar(value="Avaliacao (nosso bot): --")
        tk.Label(root, textvariable=self.eval_var, bg=COLOR_BG, fg="#9fb3c8",
                 font=("Consolas", 11), pady=4).pack(fill="x")

        self.placar_var = tk.StringVar(value="Nosso motor 0 x 0 ludolab AI (0 empates)")
        tk.Label(root, textvariable=self.placar_var, bg=COLOR_BG, fg="#9fb3c8",
                 font=("Consolas", 11), pady=8).pack(fill="x")

        self.board = [["*"] * ROWS for _ in range(COLS)]
        self.games = games
        self.events = queue.Queue()

        self._draw_board()
        threading.Thread(target=self._run,
                          args=(exe_path, depth, ai_level, our_side, games, engine_timeout),
                          daemon=True).start()
        self.root.after(100, self._poll)

    def _run(self, exe_path, depth, ai_level, our_side, games, engine_timeout):
        run_ludolab_match(exe_path, depth=depth, ai_level=ai_level, our_side=our_side,
                           headless=True, games=games, on_event=self.events.put,
                           engine_timeout=engine_timeout)

    def _draw_board(self):
        _draw_two_color_board(self.canvas, self.board)

    def _poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _handle_event(self, event):
        kind = event[0]
        if kind == "new_game":
            game_no = event[1]
            self.board = [["*"] * ROWS for _ in range(COLS)]
            self.status_var.set(f"Partida {game_no}/{self.games} em andamento...")
            self.eval_var.set("Avaliacao (nosso bot): --")
            self._draw_board()
        elif kind == "move":
            _, col, side, eval_value = event
            for row in range(ROWS):
                if self.board[col][row] == "*":
                    self.board[col][row] = side
                    break
            self._draw_board()
            quem = "nosso motor" if side == "ours" else "ludolab AI"
            if eval_value is not None:
                self.eval_var.set(f"Avaliacao (nosso bot): {eval_value}   "
                                  f"[apos lance do {quem}]")
        elif kind == "game_end":
            resultado = event[1]
            texto = {"ours": "Nosso motor venceu essa partida",
                     "ludolab": "ludolab AI venceu essa partida",
                     "empate": "Empate nessa partida"}[resultado]
            self.status_var.set(texto)
        elif kind == "final":
            placar = event[1]
            self.placar_var.set(
                f"Nosso motor {placar['ours']} x {placar['ludolab']} ludolab AI "
                f"({placar['empate']} empates)")
            self.status_var.set("Partidas concluidas.")
        elif kind == "error":
            self.status_var.set(event[1])


class EngineMatchWatchGUI:
    """Janela tkinter que mostra, em tempo real, uma partida automatica entre
    dois motores locais, sem nenhuma interacao manual. Serve ao --self-play
    (dois builds) e ao --depth-duel (mesmo build, profundidades diferentes);
    quem define o confronto e o `runner`, uma funcao que recebe o callback de
    eventos e roda run_engine_vs_engine_match ja configurado."""

    def __init__(self, root, titulo, legenda, label_a, label_b, games, runner):
        self.root = root
        self.root.title(titulo)
        self.root.configure(bg=COLOR_BG)
        self.root.resizable(False, False)

        width = COLS * CELL + 2 * PAD
        height = ROWS * CELL + 2 * PAD

        self.label_a = label_a
        self.label_b = label_b

        self.status_var = tk.StringVar(value="Iniciando...")
        tk.Label(root, textvariable=self.status_var, bg=COLOR_BG, fg="white",
                 font=("Segoe UI", 13, "bold"), pady=10).pack(fill="x")

        self.canvas = tk.Canvas(root, width=width, height=height,
                                 bg=COLOR_BG, highlightthickness=0)
        self.canvas.pack()

        tk.Label(root, text=legenda, bg=COLOR_BG, fg="#9fb3c8",
                 font=("Consolas", 10), pady=4).pack(fill="x")

        self.eval_var = tk.StringVar(value=f"Avaliacao ({label_a}): --")
        tk.Label(root, textvariable=self.eval_var, bg=COLOR_BG, fg="#9fb3c8",
                 font=("Consolas", 11), pady=4).pack(fill="x")

        self.placar_var = tk.StringVar(value=f"{label_a} 0 x 0 {label_b} (0 empates)")
        tk.Label(root, textvariable=self.placar_var, bg=COLOR_BG, fg="#9fb3c8",
                 font=("Consolas", 11), pady=8).pack(fill="x")

        self.board = [["*"] * ROWS for _ in range(COLS)]
        self.games = games
        self.events = queue.Queue()

        self._draw_board()
        threading.Thread(target=runner, args=(self.events.put,),
                          daemon=True).start()
        self.root.after(100, self._poll)

    def _draw_board(self):
        _draw_two_color_board(self.canvas, self.board, color_map=_SELFPLAY_COLOR_MAP)

    def _poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _handle_event(self, event):
        kind = event[0]
        if kind == "new_game":
            game_no = event[1]
            self.board = [["*"] * ROWS for _ in range(COLS)]
            self.status_var.set(f"Partida {game_no}/{self.games} em andamento...")
            self.eval_var.set(f"Avaliacao ({self.label_a}): --")
            self._draw_board()
        elif kind == "move":
            _, col, side, eval_value = event
            for row in range(ROWS):
                if self.board[col][row] == "*":
                    self.board[col][row] = side
                    break
            self._draw_board()
            quem = self.label_a if side == "a" else self.label_b
            if eval_value is not None:
                self.eval_var.set(f"Avaliacao ({self.label_a}): {eval_value}   "
                                  f"[apos lance do {quem}]")
        elif kind == "game_end":
            resultado = event[1]
            if resultado == "empate":
                texto = "Empate nessa partida"
            else:
                quem = self.label_a if resultado == "a" else self.label_b
                texto = f"{quem} venceu essa partida"
            self.status_var.set(texto)
        elif kind == "final":
            placar = event[1]
            self.placar_var.set(
                f"{self.label_a} {placar['a']} x {placar['b']} {self.label_b} "
                f"({placar['empate']} empates)")
            self.status_var.set("Partidas concluidas.")
        elif kind == "error":
            self.status_var.set(event[1])


class ReplayGUI:
    """Reproduz, jogada por jogada, uma partida ja salva em
    games/ludolab_games.jsonl. Nao usa o motor C++ nem o navegador -- so le
    o registro e desenha no tabuleiro, com um pequeno intervalo entre
    lances."""

    def __init__(self, root, record, delay_ms=600):
        self.root = root
        self.root.title("Connect 4 - replay")
        self.root.configure(bg=COLOR_BG)
        self.root.resizable(False, False)

        width = COLS * CELL + 2 * PAD
        height = ROWS * CELL + 2 * PAD

        lado = "primeiro" if record.get("our_side") == "player1" else "segundo"
        info = (f"{record.get('timestamp', '?')}  -  profundidade {record.get('depth', '?')}  -  "
                f"ludolab AI level {record.get('ai_level', '?')}  -  nosso motor jogou {lado}")
        tk.Label(root, text=info, bg=COLOR_BG, fg="white",
                 font=("Segoe UI", 11, "bold"), pady=8, wraplength=width).pack(fill="x")

        self.status_var = tk.StringVar(value="")
        tk.Label(root, textvariable=self.status_var, bg=COLOR_BG, fg="#9fb3c8",
                 font=("Consolas", 11), pady=4).pack(fill="x")

        self.canvas = tk.Canvas(root, width=width, height=height,
                                 bg=COLOR_BG, highlightthickness=0)
        self.canvas.pack()

        self.moves = record.get("moves", [])
        self.result = record.get("result")
        self.delay_ms = delay_ms
        self.board = [["*"] * ROWS for _ in range(COLS)]
        self.move_index = 0

        _draw_two_color_board(self.canvas, self.board)
        self.root.after(self.delay_ms, self._step)

    def _step(self):
        if self.move_index >= len(self.moves):
            nome = {"ours": "Nosso motor venceu", "ludolab": "ludolab AI venceu",
                    "empate": "Empate"}.get(self.result, "Fim da partida")
            self.status_var.set(f"{nome} -- {len(self.moves)} lances")
            return

        move = self.moves[self.move_index]
        col, side = move["col"], move["side"]
        for row in range(ROWS):
            if self.board[col][row] == "*":
                self.board[col][row] = side
                break
        _draw_two_color_board(self.canvas, self.board)
        self.move_index += 1

        quem = "nosso motor" if side == "ours" else "ludolab AI"
        self.status_var.set(f"Lance {self.move_index}/{len(self.moves)}: {quem} jogou coluna {col}")
        self.root.after(self.delay_ms, self._step)


def main():
    parser = argparse.ArgumentParser(description="Interface do Connect4")
    parser.add_argument(
        "--ludolab", action="store_true",
        help="Roda partida(s) automaticas do motor C++ contra a IA de "
             "ludolab.net, sem interacao manual, em vez de abrir a GUI local")
    parser.add_argument(
        "--self-play", action="store_true",
        help="Roda partida(s) automaticas entre dois builds do nosso motor "
             "(os executaveis em output/), metade comecando com cada um, em "
             "vez de abrir a GUI local")
    parser.add_argument("--engine-a", type=str, default=None,
                         help="Caminho do executavel do motor A no --self-play "
                              "(padrao: output/mIniMax.exe)")
    parser.add_argument("--engine-b", type=str, default=None,
                         help="Caminho do executavel do motor B no --self-play "
                              "(padrao: output/mIniMax-novo.exe)")
    parser.add_argument(
        "--depth-duel", action="store_true",
        help="Roda partida(s) de um UNICO binario contra ele mesmo em duas "
             "profundidades diferentes (--depth-a vs --depth-b), metade "
             "comecando com cada lado. Experimento separado do --self-play: a "
             "variavel em teste aqui e a profundidade, nao o executavel")
    parser.add_argument("--engine", type=str, default=None,
                         help="Caminho do executavel usado nos modos de um motor so "
                              "(--ludolab, --depth-duel e a GUI local). "
                              "Padrao: output/mIniMax.exe")
    parser.add_argument("--depth-a", type=int, default=None,
                         help="Profundidade do lado A. Obrigatoria no --depth-duel; "
                              "no --self-play e opcional (padrao: --depth), util para "
                              "equalizar builds com indexacao de profundidade diferente")
    parser.add_argument("--depth-b", type=int, default=None,
                         help="Profundidade do lado B (mesmas regras de --depth-a)")
    parser.add_argument("--time", type=int, default=0,
                         help="No --self-play, limite de tempo por lance em ms para os "
                              "dois motores (padrao: 0 = busca por profundidade). "
                              "Quando > 0, substitui a profundidade")
    parser.add_argument("--time-a", type=int, default=None,
                         help="Limite de tempo do lado A em ms (padrao: --time). Use 0 "
                              "para esse lado jogar por profundidade -- ex.: "
                              "--time-a 500 --time-b 0 --depth-b 8 poe tempo vs profundidade")
    parser.add_argument("--time-b", type=int, default=None,
                         help="Limite de tempo do lado B em ms (mesmas regras de --time-a)")
    parser.add_argument("--list-depthduel-games", action="store_true",
                         help="Lista as partidas ja salvas em games/depthduel_games.jsonl e sai")
    parser.add_argument("--list-selfplay-games", action="store_true",
                         help="Lista as partidas ja salvas em games/selfplay_games.jsonl e sai")
    parser.add_argument("--depth", type=int, default=8,
                         help="Profundidade de busca (padrao: 8). Em --ludolab, do nosso "
                              "motor; em --self-play, dos DOIS motores igualmente -- a "
                              "diferenca a testar e o executavel, nao a profundidade")
    parser.add_argument("--ai-level", type=int, default=5, choices=range(1, 11),
                         help="Nivel da IA em ludolab.net, 1 a 10 (padrao: 5)")
    parser.add_argument("--side", choices=["first", "second"], default="first",
                         help="Se o nosso motor joga primeiro ou segundo (padrao: first)")
    parser.add_argument("--games", type=int, default=1,
                         help="Quantas partidas jogar em sequencia (padrao: 1)")
    parser.add_argument("--show-browser", action="store_true",
                         help="Mostra a janela do navegador em vez de rodar headless")
    parser.add_argument("--watch", action="store_true",
                         help="Com --ludolab ou --self-play, abre uma janela mostrando "
                              "o tabuleiro em tempo real enquanto as partidas acontecem")
    parser.add_argument("--list-games", action="store_true",
                         help="Lista as partidas ja salvas em games/ludolab_games.jsonl e sai")
    parser.add_argument("--replay", type=int, metavar="N",
                         help="Reproduz a partida N numa janela (veja --list-games para os numeros)")
    parser.add_argument("--replay-delay", type=int, default=600,
                         help="Milissegundos entre cada lance no replay (padrao: 600)")
    parser.add_argument("--engine-timeout", type=int, default=180,
                         help="Segundos que se espera pela jogada do nosso motor antes de "
                              "desistir (padrao: 180). Profundidades altas (8+) sem poda "
                              "alfa-beta podem demorar bastante em certas posicoes.")
    args = parser.parse_args()

    if args.list_depthduel_games:
        records = load_depthduel_records()
        if not records:
            print(f"Nenhuma partida salva ainda em {DEPTHDUEL_LOG_PATH}.")
            return
        for i, r in enumerate(records, start=1):
            da, db = r.get("depth_a", "?"), r.get("depth_b", "?")
            res = r.get("result")
            nome = "empate" if res == "empate" else (
                f"profundidade {da if res == 'a' else db} venceu")
            print(f"{i:3d}. {r.get('timestamp', '?')}  "
                  f"{os.path.basename(r.get('engine_a', '?'))}  "
                  f"prof. {da} vs {db}  "
                  f"comecou={da if r.get('starter') == 'a' else db}  "
                  f"lances={len(r.get('moves', []))}  resultado: {nome}")
        return

    if args.list_selfplay_games:
        records = load_selfplay_records()
        if not records:
            print(f"Nenhuma partida salva ainda em {SELFPLAY_LOG_PATH}.")
            return
        nomes = {"a": "motor A venceu", "b": "motor B venceu", "empate": "empate"}
        for i, r in enumerate(records, start=1):
            print(f"{i:3d}. {r.get('timestamp', '?')}  "
                  f"A={os.path.basename(r.get('engine_a', '?'))}"
                  f"({'t=' + str(r['time_a']) + 'ms' if r.get('time_a') else 'd=' + str(r.get('depth_a', '?'))})  "
                  f"B={os.path.basename(r.get('engine_b', '?'))}"
                  f"({'t=' + str(r['time_b']) + 'ms' if r.get('time_b') else 'd=' + str(r.get('depth_b', '?'))})  "
                  f"comecou={r.get('starter', '?').upper()}  "
                  f"lances={len(r.get('moves', []))}  resultado: {nomes.get(r.get('result'), '?')}")
        return

    if args.list_games:
        records = load_game_records()
        if not records:
            print(f"Nenhuma partida salva ainda em {GAMES_LOG_PATH}.")
            return
        nomes = {"ours": "nosso motor venceu", "ludolab": "ludolab AI venceu", "empate": "empate"}
        for i, r in enumerate(records, start=1):
            lado = "primeiro" if r.get("our_side") == "player1" else "segundo"
            # partidas antigas nao registravam o executavel usado
            motor = os.path.basename(r["engine"]) if r.get("engine") else "?"
            print(f"{i:3d}. {r.get('timestamp', '?')}  {motor}  depth={r.get('depth', '?')}  "
                  f"ai_level={r.get('ai_level', '?')}  nosso motor jogou {lado}  "
                  f"lances={len(r.get('moves', []))}  resultado: {nomes.get(r.get('result'), '?')}")
        return

    if args.replay is not None:
        records = load_game_records()
        if not (1 <= args.replay <= len(records)):
            print(f"Partida {args.replay} nao existe. Use --list-games para ver as "
                  f"partidas salvas (1 a {len(records)}).")
            return
        root = tk.Tk()
        ReplayGUI(root, records[args.replay - 1], delay_ms=args.replay_delay)
        root.mainloop()
        return

    # Modos de um motor so (--ludolab e a GUI local) usam --engine quando dado
    try:
        exe_path = _resolve_engine_path(args.engine, ["mIniMax.exe", "mIniMax"])
    except FileNotFoundError as exc:
        print(exc)
        return

    if args.depth_duel:
        if args.depth_a is None or args.depth_b is None:
            print(
                "--depth-duel precisa das duas profundidades. Exemplo:\n"
                "  py Interface.py --depth-duel --depth-a 5 --depth-b 8 --games 20"
            )
            return
        if args.depth_a == args.depth_b:
            print(
                f"--depth-a e --depth-b sao iguais ({args.depth_a}); nesse caso os "
                "dois lados jogam identico e a comparacao nao diz nada.\n"
                "Use profundidades diferentes, ou --self-play para comparar builds."
            )
            return
        try:
            exe = _resolve_engine_path(args.engine, ["mIniMax.exe", "mIniMax"])
        except FileNotFoundError as exc:
            print(exc)
            return
        if not exe:
            print(
                "Nao encontrei o executavel do motor (output/mIniMax.exe).\n"
                "Compile primeiro, ou aponte o caminho com --engine:\n"
                "  g++ -O2 -o output/mIniMax.exe main.cpp Board.cpp MinMax.cpp"
            )
            return

        label_a = f"prof. {args.depth_a}"
        label_b = f"prof. {args.depth_b}"
        chart_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "games", "depthduel_results.png")

        def plot(records, path):
            return plot_depthduel_results(records, path, args.depth_a, args.depth_b)

        def runner(on_event=None):
            return run_engine_vs_engine_match(
                exe, exe, depth_a=args.depth_a, depth_b=args.depth_b,
                games=args.games, on_event=on_event,
                engine_timeout=args.engine_timeout,
                label_a=label_a, label_b=label_b,
                log_path=DEPTHDUEL_LOG_PATH, chart=(plot, chart_path))

        if args.watch:
            root = tk.Tk()
            legenda = (f"{os.path.basename(exe)}   "
                       f"Amarelo = {label_a}   Vermelho = {label_b}")
            EngineMatchWatchGUI(root, f"Connect 4 - {label_a} vs {label_b} (mesmo binario)",
                                 legenda, label_a, label_b, args.games, runner)
            root.mainloop()
        else:
            runner()
        return

    if args.self_play:
        try:
            exe_a = _resolve_engine_path(args.engine_a, ["mIniMax.exe", "mIniMax"])
        except FileNotFoundError as exc:
            print(exc)
            return
        try:
            exe_b = _resolve_engine_path(args.engine_b,
                                          ["mIniMax-novo.exe", "mIniMax-novo", "mIniMax_novo.exe"])
        except FileNotFoundError as exc:
            print(exc)
            return
        if not exe_a or not exe_b:
            faltando = []
            if not exe_a:
                faltando.append("motor A (output/mIniMax.exe)")
            if not exe_b:
                faltando.append("motor B (output/mIniMax-novo.exe)")
            print(
                "Nao encontrei: " + ", ".join(faltando) + ".\n"
                "Compile os dois builds que voce quer comparar e coloque em output/, "
                "ou aponte os caminhos com --engine-a/--engine-b. Exemplo:\n"
                "  g++ -O2 -o output/mIniMax.exe main.cpp Board.cpp MinMax.cpp\n"
                "  g++ -O2 -o output/mIniMax-novo.exe main.cpp Board.cpp MinMax.cpp"
            )
            return
        # --depth-a/--depth-b permitem equalizar builds cuja indexacao de
        # profundidade difere (por exemplo, base depth == 1 contra base
        # depth == 0, onde o mesmo numero significa um ply a mais).
        depth_a = args.depth_a if args.depth_a is not None else args.depth
        depth_b = args.depth_b if args.depth_b is not None else args.depth
        time_a = max(0, args.time_a if args.time_a is not None else args.time)
        time_b = max(0, args.time_b if args.time_b is not None else args.time)
        desc_a = _search_desc(depth_a, time_a)
        desc_b = _search_desc(depth_b, time_b)

        if os.path.abspath(exe_a) == os.path.abspath(exe_b) and desc_a == desc_b:
            print(
                "--self-play compara dois lados diferentes, mas --engine-a e "
                f"--engine-b apontam para o mesmo arquivo ({exe_a}) com a mesma "
                f"busca ({desc_a}); os dois lados jogariam identico.\n"
                "Aponte um segundo build com --engine-b, ou diferencie os lados "
                "com --depth-a/--depth-b ou --time-a/--time-b."
            )
            return

        def runner(on_event=None):
            return run_engine_vs_engine_match(
                exe_a, exe_b, depth_a=depth_a, depth_b=depth_b,
                games=args.games, on_event=on_event,
                engine_timeout=args.engine_timeout,
                time_a=time_a, time_b=time_b)

        if args.watch:
            root = tk.Tk()
            legenda = (f"Amarelo = motor A ({os.path.basename(exe_a)}, {desc_a})   "
                       f"Vermelho = motor B ({os.path.basename(exe_b)}, {desc_b})")
            EngineMatchWatchGUI(root, "Connect 4 - motor A vs motor B (self-play)",
                                 legenda, "motor A", "motor B", args.games, runner)
            root.mainloop()
        else:
            runner()
        return

    if args.ludolab:
        if not exe_path:
            print(
                "Motor nao encontrado. Compile main.cpp, Board.cpp e "
                "MinMax.cpp para output/mIniMax.exe primeiro:\n"
                "  g++ -O2 -o output/mIniMax.exe main.cpp Board.cpp MinMax.cpp"
            )
            return
        our_side = "player1" if args.side == "first" else "player2"
        if args.watch:
            root = tk.Tk()
            LudolabWatchGUI(root, exe_path, depth=args.depth, ai_level=args.ai_level,
                             our_side=our_side, games=args.games,
                             engine_timeout=args.engine_timeout)
            root.mainloop()
        else:
            run_ludolab_match(exe_path, depth=args.depth, ai_level=args.ai_level,
                               our_side=our_side, headless=not args.show_browser,
                               games=args.games, engine_timeout=args.engine_timeout)
        return

    root = tk.Tk()
    Connect4GUI(root, exe_path)
    root.mainloop()


if __name__ == "__main__":
    main()
