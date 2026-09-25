#pragma once
#include <vector>
#include <utility>

std::pair<int,int> minMax(unsigned long long pos, unsigned long long mask, int depth, bool turn, int alfa, int beta);

// Deve ser chamada uma vez, depois que column/row forem definidos, e antes
// de qualquer chamada a minMax/currentEval.
void initBottom();

// Limpa a transposition table (chamar ao iniciar uma nova partida, para nao
// deixar o cache crescer sem limite entre partidas).
void clearTP();

// Expoe o valor de eval() (privada em MinMax.cpp) so para fins de
// observacao/depuracao -- nao e usada pela busca em si.
int currentEval(unsigned long long pos, unsigned long long mask, bool playerTurn);
