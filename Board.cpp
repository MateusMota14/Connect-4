#include "Board.h"
#include <iostream>

using namespace std;

using ULL = unsigned long long;

int column, row;

int getTopInColumn(ULL mask, int col){
    ULL columnMask = 1ULL << (col * (row + 1) ) |
        1ULL << (col * (row + 1) + 1) |
        1ULL << (col * (row + 1) + 2) |
        1ULL << (col * (row + 1) + 3) |
        1ULL << (col * (row + 1) + 4) |
        1ULL << (col * (row + 1) + 5) ;

    return __builtin_popcountll(mask & columnMask);         
}

void changeBoard(ULL& pos, ULL& mask, int col, bool undoMove, bool playerTurn){
    int top = getTopInColumn(mask, col);
    undoMove ? top-- : top;

    if(row == top) return;
    if(playerTurn) pos = pos  ^ (1ULL << (col * (row +1)+ top));
    mask = mask ^ (1ULL << (col * (row +1)+ top));
    return;
}


bool gameIsOver(ULL pos, ULL mask, bool& tie){
    if(
        pos & (pos >> 1) & (pos >> 2) & (pos >> 3) || //vertical   
        pos & (pos >> (row + 1)) & (pos >> 2 * (row + 1)) & (pos >> 3 * (row + 1)) || //horizontal
        pos & (pos >> (row +2)) & (pos >> 2 * (row + 2)) & (pos >> 3 * (row + 2)) ||  // diagonal '/'  
        pos & (pos >> (row)) & (pos >> 2 * (row)) & (pos >> 3 * (row)) // diagonal secundaria '\'
    ) {
        tie = false;
        return true;
    }

    // Check for tie
    return tie = __builtin_popcountll(mask) == column * row; 
}   