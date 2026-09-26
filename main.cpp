#include <bits/stdc++.h>
#include "Board.h"
#include "MinMax.h"
#include "cassert"

using namespace std;
using ULL = unsigned long long;

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);

    column = 7;
    row = 6;
    initBottom();
    int depth = 5;
    int timeLimitMs = 0; // 0 = sem limite de tempo, so profundidade
    ULL pos = 0, mask = 0;
    int lastMove = -1;
    bool turn = true; 

    string cmd;
    while (cin >> cmd) {
        if (cmd == "depth") {
            cin >> depth;
            if (depth < 1) depth = 1;
        }
        else if (cmd == "time") {
            cin >> timeLimitMs;
            if (timeLimitMs < 0) timeLimitMs = 0;
        }
        else if (cmd == "new") {
            int starter;
            cin >> starter;
            pos = 0;
            mask = 0;
            lastMove = -1;
            turn = (starter == 1);
            clearTt();

            if (!turn) {
                int maxDepth = timeLimitMs > 0 ? column * row : depth;
                auto move = searchBestMove(pos, mask, turn, maxDepth, timeLimitMs);
                changeBoard(pos , mask, move.second, false, false);
                lastMove = move.second;
                turn = !turn;
                cout << "move " << lastMove << "\n";
                cout << "eval " << currentEval(pos, mask, true) << "\n" << flush;
            }
        }
        else if (cmd == "play") {
            int col;
            cin >> col;
            if (col >= 0 && col < column && getTopInColumn(mask, col) < row) {
                changeBoard(pos, mask, col, false, true);
                lastMove = col;
                turn = false;
                cout << "eval " << currentEval(pos, mask, true) << "\n" << flush;
                cout<<"pos: "<< currentEval(pos, mask, true)<<"pos ^ mask: "<< currentEval(pos ^ mask, mask, true)<<"\n"<< flush;

                int maxDepth = timeLimitMs > 0 ? column * row : depth;
                auto move = searchBestMove(pos ^ mask, mask, turn, maxDepth, timeLimitMs);
                changeBoard(pos, mask, move.second, false, false);
                lastMove = move.second;
                turn = true;
                cout << "move " << lastMove << "\n";
                cout << "eval " << currentEval(pos, mask, true) << "\n" << flush;
            }
            assert((currentEval(pos, mask, true) == -currentEval(pos ^ mask, mask, true)) && "Erro: A avaliacao de pos e pos^mask nao bateu!");
        }
        else if (cmd == "quit") {
            break;
        }
    }

    return 0;
}
