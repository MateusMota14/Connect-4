#include "MinMax.h"
#include "Board.h"
#include <climits>
#include <map>

using namespace std;

using ULL = unsigned long long;

namespace
{
    int cols[] = {3, 2, 4, 1, 5, 0, 6};
    ULL bottom = 0;

    map<ULL, int> tt;

    int eval(ULL pos, ULL mask, bool playerTurn)
    {
        int eval = 0;
        if (!playerTurn)
        {
            pos = pos ^ mask;
        }

        for (int col = 0; col < column; ++col)
        {
            int top = getTopInColumn(mask, col);

            for (int vert = 0; vert <= top; vert++)
            {
                if (pos & (1ULL << (col * (row + 1) + vert)))
                {
                    if (col == 0 || col == column - 1)
                        eval += 1;
                    else if (col == 1 || col == column - 2)
                        eval += 2;
                    else if (col == 2 || col == column - 3)
                        eval += 3;
                    else
                        eval += 5;
                }
                else if (mask & (1ULL << (col * (row + 1) + vert)))
                {
                    if (col == 0 || col == column - 1)
                        eval -= 1;
                    else if (col == 1 || col == column - 2)
                        eval -= 2;
                    else if (col == 2 || col == column - 3)
                        eval -= 3;
                    else
                        eval -= 5;
                }
            }
        }

        // Vertical evaluation on windows of 4
        for (int col = 0; col < column; ++col)
        {
            int top = getTopInColumn(mask, col);
            for (int vert = 0; vert <= top - 3; ++vert)
            {
                int played = 0;
                int opponent = 0;
                for (int i = 0; i < 4; ++i)
                {
                    bool occupied = mask & (1ULL << (col * (row + 1) + vert + i));
                    bool playerPiece = pos & (1ULL << (col * (row + 1) + vert + i));
                    if (occupied)
                    {
                        if (playerPiece)
                            played++;
                        else
                            opponent++;
                    }
                }
                if (played && opponent)
                    continue; // Mixed window, no score

                if (played == 4)
                    eval = 1e9;
                else if (played == 3)
                    eval += 50;
                else if (played == 2)
                    eval += 5;

                if (opponent == 4)
                    eval = -1e9;
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
                int played = 0;
                int opponent = 0;
                for (int i = 0; i < 4; ++i)
                {
                    bool occupied = mask & (1ULL << ((hor + i) * (row + 1) + rowIdx));
                    bool playerPiece = pos & (1ULL << ((hor + i) * (row + 1) + rowIdx));
                    if (occupied)
                    {
                        if (playerPiece)
                            played++;
                        else
                            opponent++;
                    }
                }
                if (played && opponent)
                    continue; // Mixed window, no score
                if (played == 4)
                    eval = 1e9;
                else if (played == 3)
                    eval += 50;
                else if (played == 2)
                    eval += 5;

                if (opponent == 4)
                    eval = -1e9;
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
                int played = 0;
                int opponent = 0;

                for (int i = 0; i < 4; i++)
                {
                    bool occupied = mask & (1ULL << ((col + i) * (row + 1) + rowIdx + i));
                    bool playerPiece = pos & (1ULL << ((col + i) * (row + 1) + rowIdx + i));

                    if (occupied)
                    {
                        if (playerPiece)
                            played++;
                        else
                            opponent++;
                    }
                }

                if (played && opponent)
                    continue; // Mixed window, no score
                if (played == 4)
                    eval = 1e9;
                else if (played == 3)
                    eval += 50;
                else if (played == 2)
                    eval += 5;

                if (opponent == 4)
                    eval = -1e9;
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
                int played = 0;
                int opponent = 0;

                for (int i = 0; i < 4; i++)
                {
                    bool occupied = mask & (1ULL << ((col + i) * (row + 1) + rowIdx - i));
                    bool playerPiece = pos & (1ULL << ((col + i) * (row + 1) + rowIdx - i));

                    if (occupied)
                    {
                        if (playerPiece)
                            played++;
                        else
                            opponent++;
                    }
                }

                if (played && opponent)
                    continue; // Mixed window, no score
                if (played == 4)
                    eval = 1e9;
                else if (played == 3)
                    eval += 50;
                else if (played == 2)
                    eval += 5;

                if (opponent == 4)
                    eval = -1e9;
                else if (opponent == 3)
                    eval -= 50;
                else if (opponent == 2)
                    eval -= 5;
            }
        }

        return eval;
    }

} // namespace

void initBottom()
{
    bottom = 0;
    for (int i = 0; i < column; i++)
    {
        bottom |= (1ULL << (i * (row + 1)));
    }
}

void clearTP()
{
    tt.clear();
}

int currentEval(ULL pos, ULL mask, bool playerTurn)
{
    return eval(pos, mask, playerTurn);
}

pair<int, int> minMax(ULL pos, ULL mask, int depth, bool playerTurn, int alfa, int beta)
{
    bool tie;

    if (gameIsOver(pos ^ mask, mask, tie))
    {
        if (tie)
            return {0, 0};
        if (!playerTurn)
            return {1e9 - depth, 0};
        return {-1e9 + depth, 0};
    }

    if (playerTurn)
    {
        int mx = INT_MIN;
        int mark = -1;

        for (int col : cols)
        {
            if (getTopInColumn(mask, col) == row)
                continue;
            changeBoard(pos, mask, col, false, true);

            if(depth == 0){
                auto temp = eval(pos, mask, playerTurn);

                if (temp > mx){
                    mx = temp;
                    mark = col;
                }

                alfa = max(alfa, temp);
            }

            else {
                auto temp = minMax(pos ^ mask, mask, depth - 1, !playerTurn, alfa, beta);

                if (temp.first > mx){
                    mx = temp.first;
                    mark = col;
                }

                alfa = max(alfa, temp.first);
            }

            changeBoard(pos, mask, col, true, true);

            if (alfa >= beta)
                break;
        }
        return {mx, mark};
    }
    else
    {
        int mn = INT_MAX;
        int mark = -1;

        for (int col : cols)
        {
            if (getTopInColumn(mask, col) == row)
                continue;
            changeBoard(pos, mask, col, false, true);

            if(depth == 0){
                auto temp = eval(pos, mask, playerTurn);
                if (temp < mn){
                    mn = temp;
                    mark = col;
                }

                beta = min(beta, temp);
            }

            else {
                auto temp = minMax(pos ^ mask, mask, depth - 1, !playerTurn, alfa, beta);
                if (temp.first < mn){
                    mn = temp.first;
                    mark = col;
                }

                beta = min(beta, temp.first);

            }

            changeBoard(pos, mask, col, true, true);

            if (alfa >= beta)
                break;
        }
        return {mn, mark};
    }
}
