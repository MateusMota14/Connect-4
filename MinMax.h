#pragma once
#include <vector>
#include <utility>

std::pair<int,int> minMax(unsigned long long pos, unsigned long long mask, int depth, bool turn, int alfa, int beta, int firstMove = -1);
// Busca com iterative deepening, da profundidade 0 ate maxDepth, parando antes
// se o tempo acabar ou se encontrar vitoria/derrota forcada. Devolve
// {avaliacao, coluna} da ultima profundidade que terminou por completo.
// timeLimitMs <= 0 significa sem limite de tempo (so profundidade).
std::pair<int,int> searchBestMove(unsigned long long pos, unsigned long long mask,bool turn, int maxDepth, int timeLimitMs);

// Deve ser chamada uma vez, depois que column/row forem definidos, e antes
// de qualquer chamada a minMax/currentEval.
void initBottom();

// Limpa a transposition table (chamar ao iniciar uma nova partida, para nao
// deixar o cache crescer sem limite entre partidas).
void clearTt();

// Expoe o valor de eval() (privada em MinMax.cpp) so para fins de
// observacao/depuracao -- nao e usada pela busca em si.
int currentEval(unsigned long long pos, unsigned long long mask, bool playerTurn);
