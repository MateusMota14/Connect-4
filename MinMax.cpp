#include "MinMax.h"
#include "Board.h"
#include <chrono>
#include <climits>
#include <cstdlib>
#include <unordered_map>

using namespace std;

using ULL = unsigned long long;

namespace
{
    int cols[] = {3, 2, 4, 1, 5, 0, 6};
    ULL bottom = 0;
    
    chrono::steady_clock::time_point prazo;
    bool usaPrazo = false;
    bool abortado = false;
    long long nos = 0;

    // flag: o que "eval" significa em relacao ao valor verdadeiro da posicao
    enum { EXACT = 0, UPPER = 1, LOWER = 2 };

    struct Entry {
        int eval;       // valor que a busca devolveu
        int depth;      // profundidade RESTANTE com que o no foi buscado
        int bestMove;
        int flag;       // EXACT, UPPER (valor <= eval) ou LOWER (valor >= eval)
    };
    unordered_map<ULL, Entry> tt;

    int eval(ULL pos, ULL mask, bool playerTurn)
    {
        int eval = 0;
        if (!playerTurn)
        {
            pos = pos ^ mask;
        }

        for (int col = 0; col < column; ++col)
        {
            ULL columnMask = 1ULL << (col * (row + 1) ) |
            1ULL << (col * (row + 1) + 1) |
            1ULL << (col * (row + 1) + 2) |
            1ULL << (col * (row + 1) + 3) |
            1ULL << (col * (row + 1) + 4) |
            1ULL << (col * (row + 1) + 5) ;

            int diff = 2 * __builtin_popcountll(pos & columnMask) - __builtin_popcountll(mask & columnMask);//quantity of pieces by player - opponent in column
            if (diff == 0) continue;
            
            if (col == 0 || col == column - 1)
                eval += diff;
            else if (col == 1 || col == column - 2)
                eval += 2 * diff;
            else if (col == 2 || col == column - 3)
                eval += 3 *diff;
            else
                eval += 5 * diff;
        }

        // Vertical evaluation on windows of 4
        for (int col = 0; col < column; ++col)
        {
            for (int vert = 0; vert + 3 < row; ++vert)
            {
                ULL windowMask = 1ULL << (col * (row + 1) + vert ) | 1ULL << (col * (row + 1) + vert + 1) | 1ULL << (col * (row + 1) + vert + 2) | 1ULL << (col * (row + 1) + vert + 3);
                ULL occupied = mask & windowMask;
                ULL playerPiece = pos & windowMask;
                
                auto played = __builtin_popcountll(playerPiece);
                auto opponent = __builtin_popcountll(occupied) - played;

                if (played && opponent)
                    continue; // Mixed window, no score

                if (played == 4)
                    return eval = 1e9;
                else if (played == 3)
                    eval += 50;
                else if (played == 2)
                    eval += 5;

                if (opponent == 4)
                    return eval = -1e9;
                else if (opponent == 3)
                    eval -= 50;
                else if (opponent == 2)
                    eval -= 5;
            }
        }

        // Horizontal evaluation on windows of 4
        for (int rowIdx = 0; rowIdx < row; ++rowIdx)
        {
            for (int hor = 0; hor <= column - 4; ++hor)
            {
                ULL windowMask = 1ULL << (hor * (row + 1) + rowIdx) | 1ULL << ((hor + 1) * (row + 1) + rowIdx) | 1ULL << ((hor + 2) * (row + 1) + rowIdx) | 1ULL << ((hor + 3) * (row + 1) + rowIdx);
                ULL occupied = mask & windowMask;
                ULL playerPiece = pos & windowMask;

                auto played = __builtin_popcountll(playerPiece);
                auto opponent = __builtin_popcountll(occupied) - played;
                
                if (played && opponent)
                    continue; // Mixed window, no score
                if (played == 4)
                    return eval = 1e9;
                else if (played == 3)
                    eval += 50;
                else if (played == 2)
                    eval += 5;

                if (opponent == 4)
                    return eval = -1e9;
                else if (opponent == 3)
                    eval -= 50;
                else if (opponent == 2)
                    eval -= 5;
            }
        }

        // Primary diagonal evaluation on windows of 4
        for (int col = 0; col + 3 < column; col++)
        {
            for (int rowIdx = 0; rowIdx + 3 < row; rowIdx++)
            {
                ULL windowMask = 1ULL << ((col + 0) * (row + 1) + rowIdx + 0) | 1ULL << ((col + 1) * (row + 1) + rowIdx + 1) | 1ULL << ((col + 2) * (row + 1) + rowIdx + 2) | 1ULL << ((col + 3) * (row + 1) + rowIdx + 3);
                ULL occupied = mask & windowMask;
                ULL playerPiece = pos & windowMask;

                auto played = __builtin_popcountll(playerPiece);
                auto opponent = __builtin_popcountll(occupied) - played;

                if (played && opponent)
                    continue; // Mixed window, no score
                if (played == 4)
                    return eval = 1e9;
                else if (played == 3)
                    eval += 50;
                else if (played == 2)
                    eval += 5;

                if (opponent == 4)
                    return eval = -1e9;
                else if (opponent == 3)
                    eval -= 50;
                else if (opponent == 2)
                    eval -= 5;
            }
        }

        // Secondary diagonal evaluation on windows of 4
        for (int col = 0; col + 3 < column; col++)
        {
            for (int rowIdx = row - 1; rowIdx >= 3; rowIdx--)
            {   
                ULL windowMask = 1ULL << ((col + 0) * (row + 1) + rowIdx - 0) | 1ULL << ((col + 1) * (row + 1) + rowIdx - 1) | 1ULL << ((col + 2) * (row + 1) + rowIdx - 2) | 1ULL << ((col + 3) * (row + 1) + rowIdx - 3);
                ULL occupied = mask & windowMask;
                ULL playerPiece = pos & windowMask;

                auto played = __builtin_popcountll(playerPiece);
                auto opponent = __builtin_popcountll(occupied) - played;

                if (played && opponent)
                    continue; // Mixed window, no score
                if (played == 4)
                    return eval = 1e9;
                else if (played == 3)
                    eval += 50;
                else if (played == 2)
                    eval += 5;

                if (opponent == 4)
                    return eval = -1e9;
                else if (opponent == 3)
                    eval -= 50;
                else if (opponent == 2)
                    eval -= 5;
            }
        }

        return eval;
    }

} //nasmesoace

void initBottom()
{
    bottom = 0;
    for (int i = 0; i < column; i++)
    {
        bottom |= (1ULL << (i * (row + 1)));
    }
}

void clearTt()
{
    tt.clear();
    for (ULL t : {0ULL, 1ULL << 63}) tt[bottom | t] = {0, 100, 3, EXACT};
}

int currentEval(ULL pos, ULL mask, bool playerTurn)
{
    return eval(pos, mask, playerTurn);
}

pair<int, int> minMax(ULL pos, ULL mask, int depth, bool playerTurn, int alfa, int beta, int firstMove)
{
    if (usaPrazo && (++nos & 1023) == 0 && chrono::steady_clock::now() >= prazo)
        abortado = true;

    if (abortado)
        return {0, -1};

    bool tie;
    if (gameIsOver(pos ^ mask, mask, tie))
    {
        if (tie)
            return {0, 0};
        if (!playerTurn)
        return {1e9 + depth, 0};
    return {-1e9 - depth, 0};
    }

    ULL key = ((playerTurn ? pos : pos ^ mask) + mask + bottom) | ((ULL)playerTurn << 63);
    auto it = tt.find(key);
    
    if (it != tt.end()){
        auto cachedDepth = it->second.depth;
        firstMove = it->second.bestMove;

        if (cachedDepth >= depth){
            if (it->second.flag == 0)
                return {it->second.eval, firstMove};
            else if (it->second.flag == 2)
                alfa = max(alfa, it->second.eval);
            else if (it->second.flag == 1)
                beta = min(beta, it->second.eval);
            if (alfa >= beta)
                return {it->second.eval, firstMove};
        }
    }
    int flag, alfa0 =alfa, beta0 = beta;

    int order[7] , n =0;
    if (firstMove != -1) order[n++] = firstMove;

    for (int c : cols)
        if (c != firstMove) order[n++] = c;

    if (playerTurn)
    {
        int mx = INT_MIN;
        int move = -1;

        for (int col : order)
        {
            if (getTopInColumn(mask, col) == row )
                continue;
            
            changeBoard(pos, mask, col, false, true);
            if(depth == 0){
                auto temp = eval(pos, mask, playerTurn);

                if (temp > mx){
                    mx = temp;
                    move = col;
                }

                alfa = max(alfa, temp);
            }

            else {
                auto temp = minMax(pos ^ mask, mask, depth - 1, !playerTurn, alfa, beta, -1);

                if (temp.first > mx){
                    mx = temp.first;
                    move = col;
                }

                alfa = max(alfa, temp.first);
            }

            changeBoard(pos, mask, col, true, true);

            if (alfa >= beta)
                break;
        }
        
        if(mx > alfa0 && mx < beta0) flag =0;
        else if (mx <= alfa0) flag =1;
        else if (mx >= beta0) flag =2;

        if(!abortado) tt[key] = {mx, depth, move, flag};
        return {mx, move};
    }
    else
    {
        int mn = INT_MAX;
        int move = -1;

        for (int col : order)
        {
            if (getTopInColumn(mask, col) == row)
                continue;
            changeBoard(pos, mask, col, false, true);

            if(depth == 0){
                auto temp = eval(pos, mask, playerTurn);
                if (temp < mn){
                    mn = temp;
                    move = col;
                }

                beta = min(beta, temp);
            }

            else {
                auto temp = minMax(pos ^ mask, mask, depth - 1, !playerTurn, alfa, beta, -1);
                if (temp.first < mn){
                    mn = temp.first;
                    move = col;
                }

                beta = min(beta, temp.first);

            }

            changeBoard(pos, mask, col, true, true);

            if (alfa >= beta)
                break;
        }

        if(mn > alfa0 && mn < beta0) flag =0;
        else if (mn <= alfa0) flag =1;
        else if (mn >= beta0) flag =2;

        if(!abortado) tt[key] = {mn, depth, move, flag};
        return {mn, move};
    }
}

std::pair<int,int> searchBestMove(unsigned long long pos, unsigned long long mask,bool turn, int maxDepth, int timeLimitMs){    
    auto inicio = chrono::steady_clock::now();
    auto move = minMax(pos, mask, 0, turn, INT_MIN, INT_MAX, -1);
    prazo = inicio + chrono::milliseconds(timeLimitMs);

    
    if(timeLimitMs > 0){ 
        usaPrazo = true;
    }

    for(int depth = 1; depth <= maxDepth; depth++){
        if (abs(move.first) >= 5e8) break; 
        
        auto result = minMax(pos, mask, depth, turn, INT_MIN, INT_MAX, move.second);
        if(abortado) break;
        move = result;
    }
    
    abortado = false; nos =0; usaPrazo = false;
    return move;
}