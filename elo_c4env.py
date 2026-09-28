"""
Mede o Elo do nosso motor C++ na escala do Connect-4-env
(https://github.com/lucasBertola/Connect-4-env), jogando contra os bots de
referencia do pacote (BabyPlayer = 1000 ... SelfTrained7Player = 2573).

A escala e interna ao pacote: o numero so vale em relacao a esses bots.

Requer: pip install --user torch --index-url https://download.pytorch.org/whl/cpu
        pip install --user git+https://github.com/lucasBertola/Connect-4-env

Dois modos:
  - leaderboard (padrao): o calculo do proprio pacote, que joga contra os 2 bots
    de Elo mais proximo e vai ajustando. Com --watch, mostra as partidas.
      python3 elo_c4env.py --engine output/ttcentro --time 100 --matches 100
  - duelo (--duel N): N partidas direto contra o SelfTrained6 (2410) e o
    SelfTrained7 (2573), em paralelo e sem janela; o Elo sai do placar.
      python3 elo_c4env.py --engine output/ttcentro --time 1000 --duel 100
"""

import argparse
import math
import multiprocessing as mp
import subprocess

import numpy as np
from connect_four_gymnasium.ConnectFourEnv import ConnectFourEnv
from connect_four_gymnasium.players.Player import Player
from connect_four_gymnasium.tools.EloLeaderboard import EloLeaderboard


class EnginePlayer(Player):
    """Adapta o motor ao ambiente: cada lance e pedido com o comando
    "board <42 casas>", porque o ambiente entrega o tabuleiro inteiro (e nao
    o historico de lances). O motor fica aberto entre os lances."""

    def __init__(self, exe_path, depth=8, time_ms=0, name="NossoMotor"):
        self.name = name
        self.process = subprocess.Popen([exe_path], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, text=True, bufsize=1)
        self._send(f"depth {depth}")
        if time_ms:
            self._send(f"time {time_ms}")

    def _send(self, cmd):
        self.process.stdin.write(cmd + "\n")
        self.process.stdin.flush()

    @staticmethod
    def _to_board_string(obs):
        # obs: matriz 6x7, linha 0 no topo; 1 = peca de quem joga (o motor),
        # -1 = peca do adversario, 0 = vazia -> '1', '2', '0'
        return "".join("1" if v == 1 else "2" if v == -1 else "0"
                       for v in np.asarray(obs).reshape(-1))

    def _play_single(self, obs):
        self._send("board " + self._to_board_string(obs))
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("o motor C++ encerrou inesperadamente")
            if line.startswith("move"):
                col = int(line.split()[1])
                break
        # lance ilegal perde a partida no ambiente: por seguranca, cai para
        # a primeira coluna livre (nao deve acontecer)
        if not (0 <= col < 7) or obs[0, col] != 0:
            col = next(c for c in range(7) if obs[0, c] == 0)
        return col

    def play(self, observation):
        if isinstance(observation, list):
            return [self._play_single(o) for o in observation]
        return self._play_single(observation)

    def getName(self):
        return self.name

    def getElo(self):
        return None

    def isDeterministic(self):
        return True

    def close(self):
        try:
            self._send("quit")
        except Exception:
            pass
        self.process.terminate()


def play_game(env, player):
    """Joga uma partida completa no ambiente; devolve 1 (vitoria), 0 ou -1."""
    obs, _ = env.reset()
    while True:
        obs, reward, done, truncated, _ = env.step(player.play(obs))
        if done or truncated:
            return int(np.sign(reward))


class WatchedEloLeaderboard(EloLeaderboard):
    """Mesmo calculo de Elo do pacote, mas as partidas rodam uma de cada vez
    numa janela (render_mode="human" do proprio ambiente). Usa um unico
    ambiente, trocando so o adversario, para a janela ser criada uma vez e nao
    reaparecer na frente das outras a cada partida."""

    def __init__(self):
        super().__init__()
        self.env = None

    def get_scores(self, player, opponents):
        scores = []
        for opponent in opponents:
            if self.env is None:
                self.env = ConnectFourEnv(opponent=opponent, render_mode="human",
                                          main_player_name=player.getName())
            else:
                self.env.change_opponent(opponent)
            reward = play_game(self.env, player)
            resultado = {1: "vitoria", 0: "empate", -1: "derrota"}[reward]
            print(f"  vs {opponent.getName()} ({opponent.getElo()}): {resultado}", flush=True)
            scores.append(reward)
        return scores


# ----------------------------------------------------------------- duelo

DUEL_OPPONENTS = ["SelfTrained6Player", "SelfTrained7Player"]


def _duel_worker(task):
    """Roda num processo separado: um motor e um adversario proprios."""
    exe, depth, time_ms, opp_name, games, seed = task
    import torch
    import connect_four_gymnasium.players as players
    torch.set_num_threads(1)
    np.random.seed(seed)
    opponent = getattr(players, opp_name)()
    player = EnginePlayer(exe, depth=depth, time_ms=time_ms)
    env = ConnectFourEnv(opponent=opponent)
    placar = {1: 0, 0: 0, -1: 0}
    try:
        for _ in range(games):
            placar[play_game(env, player)] += 1
    finally:
        player.close()
    return opp_name, placar


def _expected(r, r_opp):
    return 1 / (1 + 10 ** ((r_opp - r) / 400))


def _performance_elo(results, elos):
    """Elo R que faz os pontos esperados baterem com os pontos obtidos
    (maxima verossimilhanca do modelo de Elo), por bissecao."""
    games = sum(sum(p.values()) for p in results.values())
    points = sum(p[1] + 0.5 * p[0] for p in results.values())
    if points <= 0 or points >= games:
        return None   # 0% ou 100%: o Elo nao tem valor finito
    lo, hi = -2000.0, 6000.0
    for _ in range(100):
        mid = (lo + hi) / 2
        exp = sum(sum(p.values()) * _expected(mid, elos[o]) for o, p in results.items())
        lo, hi = (mid, hi) if exp < points else (lo, mid)
    return (lo + hi) / 2


def run_duel(exe, depth, time_ms, games, workers, seed=0):
    import connect_four_gymnasium.players as players
    elos = {name: getattr(players, name)().getElo() for name in DUEL_OPPONENTS}
    # divide as partidas de cada adversario entre os processos
    tasks = []
    per = max(1, workers // len(DUEL_OPPONENTS))
    for name in DUEL_OPPONENTS:
        base, extra = divmod(games, per)
        for i in range(per):
            n = base + (1 if i < extra else 0)
            if n:
                tasks.append((exe, depth, time_ms, name, n, seed))
                seed += 1
    results = {name: {1: 0, 0: 0, -1: 0} for name in DUEL_OPPONENTS}
    with mp.get_context("spawn").Pool(len(tasks)) as pool:
        for name, placar in pool.imap_unordered(_duel_worker, tasks):
            for k in placar:
                results[name][k] += placar[k]
    for name in DUEL_OPPONENTS:
        p = results[name]
        n = sum(p.values())
        pts = (p[1] + 0.5 * p[0]) / n
        perf = _performance_elo({name: p}, elos)
        perf_txt = f"{perf:.0f}" if perf is not None else ("acima da escala" if pts >= 1 else "abaixo da escala")
        print(f"  vs {name} ({elos[name]}): {p[1]} V  {p[0]} E  {p[-1]} D  "
              f"-> {100 * pts:.1f}% dos pontos, desempenho {perf_txt}")
    elo = _performance_elo(results, elos)
    return elo


def main():
    parser = argparse.ArgumentParser(description="Elo do motor na escala do Connect-4-env")
    parser.add_argument("--engine", default="output/ttcentro", help="executavel do motor")
    parser.add_argument("--depth", type=int, default=8, help="profundidade (se --time for 0)")
    parser.add_argument("--time", type=int, default=100, help="ms por lance (0 = usa --depth)")
    parser.add_argument("--matches", type=int, default=100,
                        help="rodadas do EloLeaderboard (cada uma = 2 partidas)")
    parser.add_argument("--watch", action="store_true",
                        help="mostra cada partida numa janela (uma de cada vez, mais lento)")
    parser.add_argument("--duel", type=int, default=0, metavar="N",
                        help="em vez do leaderboard, joga N partidas contra o SelfTrained6 "
                             "e N contra o SelfTrained7, em paralelo e sem janela")
    parser.add_argument("--workers", type=int, default=8,
                        help="processos em paralelo no --duel (padrao: 8)")
    parser.add_argument("--seed", type=int, default=0,
                        help="semente inicial do --duel; use valores diferentes para que rodadas "
                             "repetidas tenham partidas diferentes (padrao: 0)")
    args = parser.parse_args()

    busca = f"{args.time} ms por lance" if args.time else f"profundidade {args.depth}"

    if args.duel:
        print(f"Duelo de {args.engine} ({busca}): {args.duel} partidas contra cada um de "
              f"{', '.join(DUEL_OPPONENTS)}...")
        elo = run_duel(args.engine, args.depth, args.time, args.duel, args.workers, args.seed)
        if elo is None:
            print("Elo fora da escala (0% ou 100% dos pontos).")
        else:
            print(f"Elo na escala do Connect-4-env: {elo:.0f}")
        return

    player = EnginePlayer(args.engine, depth=args.depth, time_ms=args.time)
    try:
        print(f"Calculando o Elo de {args.engine} ({busca}), {args.matches} rodadas...")
        board = WatchedEloLeaderboard() if args.watch else EloLeaderboard()
        elo = board.get_elo(player, num_matches=args.matches)
        print(f"Elo na escala do Connect-4-env: {elo:.0f}")
    finally:
        player.close()


if __name__ == "__main__":
    main()
