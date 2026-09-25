#pragma once
#include <vector>

// Board dimensions: column = number of columns, row = number of rows. Set
// once in main() before any other board function is used.
extern int column, row;

int getTopInColumn(std::vector<std::vector<char>>& state, int col);
void makeMove(std::vector<std::vector<char>>& state, int col, bool turn);
bool gameIsOver(std::vector<std::vector<char>>& state, int lastMove, bool& tie, bool& computerWon);

int getTopInColumn(unsigned long long mask, int col);
void changeBoard(unsigned long long& pos, unsigned long long& mask, int col, bool undoMove, bool playerTurn);
bool gameIsOver(unsigned long long pos, unsigned long long mask, bool& tie);