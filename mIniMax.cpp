#include <bits/stdc++.h>
using namespace std;
int n,m;
bool player1;

void display(vector<vector<char>>& state){
    for(int i=m-1;i>=0 ;i--){
        for(int j=0; j<n ; j++){
            cout<<state[j][i];
        }
        cout<<"\n";
    }
}

bool gameIsOver(vector<vector<char>>& state,int lastMove, bool& tie,  bool& computerWon){
    if(lastMove ==-1) return false;//game board is empty
    int row =-1;   
    for(int i = m-1;i>=0;i--){
        if(state[lastMove][i] !='*') {row = i;break;}
    }
    //checking rows for victories
    
    for(int i=0;i<4;++i){
        if(lastMove - i >=0 && lastMove +(3-i) <=n-1 && state[lastMove -i][row] == state[lastMove -i+1][row] && state[lastMove -i][row] == state[lastMove -i+2][row] && state[lastMove -i][row] == state[lastMove -i+3][row]){
            if(state[lastMove][row] == 'x') computerWon =false;
            else computerWon =true;
            return true;
        }
    }
    
    //checking columns 
    for(int i=0;i<4;++i){
        if(row - i >=0 && row +(3-i) <=m-1 && state[lastMove][row-i] == state[lastMove][row -i +1] && state[lastMove][row -i] == state[lastMove][row -i +2] && state[lastMove][row -i +3] == state[lastMove][row -i]){
            if(state[lastMove][row] == 'x') computerWon =false;
            else computerWon =true;
            return true;
        }
    }
    
    //checking diagonals for victories
    //ascending diagonal:
    for(int i =0;i<4;++i){
        if(row +(3-i) <=m-1 && lastMove +(3-i) <=n-1 && row -i >=0 && lastMove -i >=0 && state[lastMove -i][row -i] == state[lastMove -i+1][row -i +1] && state[lastMove -i][row -i] == state[lastMove -i+2][row -i +2] && state[lastMove -i][row-i] == state[lastMove -i+3][row -i+3]){
            if(state[lastMove][row] == 'x') computerWon =false;
            else computerWon =true;
            return true;   
        }
    }
  
    //descending diagonal:  
    for(int i =0;i<4;++i){
        if(row -(3-i) >=0 && lastMove +(3-i) <=n-1 && row +i <=m-1 && lastMove -i >=0 && state[lastMove -i][row +i] == state[lastMove -i+1][row +i -1] && state[lastMove -i][row +i] == state[lastMove -i+2][row +i -2] && state[lastMove -i][row+i] == state[lastMove -i+3][row +i-3]){
            if(state[lastMove][row] == 'x') computerWon =false;
            else computerWon =true;
            return true;   
        }
    }
    
    if(row !=m-1) return false;
    else{
        for(int i=0;i<n;++i) {
            if(state[i][m-1] =='*') return false; 
        }
    }

    tie = true;
    return true;
}
int getTopInColumn(vector<vector<char>>& state, int i){//this function searchs in a column for the element different than '*' that is at the top
    for(int j= m-1; j>=0;j--){
        if(state[i][j] !='*'){
            return j;
        }
    }
    return -1;
}

void makeMove(vector<vector<char>>& state, int i, bool turn){
    int k = getTopInColumn(state, i);
    if(m-1 == k) return;

    if(turn) state[i][k+1] = 'x';
    else state[i][k+1] = 'o';

    return;
}

int eval(vector<vector<char>>& state, bool turn, int lastMove){
    int ans=0;
    
    if(lastMove == 3) turn? ans+=10 :ans-=10;
    else if(lastMove == 2 ||lastMove == 4) turn? ans+=5 :ans-=5;
    else if (lastMove == 0 ||lastMove == 6)  turn? ans-=2 :ans+=2;
    

    //check columns 
    for(int i=0;i<n;i++){
        int k = getTopInColumn(state, i);
        if(k==-1) continue;
        int j=k;
        int count =0;
        
        while(j>=0 && state[i][k] == state[i][j]){
            count++;
            j--;
        }
        state[i][k] =='x'? ans+=count :ans-=count;
    }
    //check rows. Rows are more importante than columns 
    for(int i=0;i<m;++i){
        int j =0;
        while(j<n-1 && state[j][i] == '*') j++;
        char c = state[j][i];
        int count =0;
        while(j<n-1 && state[j][i] == c) {count++;j++;}
        if(j<n-1 && state[j][i]!='*') continue;
        
        if(count == 3) turn? ans = 20000: ans-=20000;
        else if(count ==2) turn? ans = 5: ans-=5;
        else turn?ans+=count :ans-=count;
    }

    return ans;

}


pair<int,int> minMax(vector<vector<char>> state,int depth, bool turn, int lastMove){
    if(lastMove==-1)return{10,3};// board is empty, the best move is the middle
    bool tie, computerWon;
    if (gameIsOver(state,lastMove, tie, computerWon)) {
        if (tie) return {0,0};
        if (computerWon) return{ -20000 ,0};
        return {20000 ,0};
    }
    
    if(depth ==1){
        int mark =-1;
        if(turn){
            int mx = -30000;
           
            for(int i=0;i<n;++i){
                if(state[i][m-1] !='*' ) continue;
                makeMove(state, i, turn);
                
                int temp = eval(state,turn,i);            
                
                int k =getTopInColumn(state, i);
                state[i][k] = '*';
        
                if(temp>mx){
                    mx = temp;
                    mark = i;
                }
            }
            return {mx,mark};
        }

        else{
            int mn = 30000;
           
            for(int i=0;i<n;++i){
                if(state[i][m-1] !='*' ) continue;
                makeMove(state, i, turn);
                
                int temp = eval(state,turn,i);            
                
                int k =getTopInColumn(state, i);
                state[i][k] = '*';
        
                if(temp <mn){
                    mn = temp;
                    mark = i;
                }
            }
            return {mn,mark};
        }
    }

    else {
        if(turn){
            int mx = -30000;
            int mark =-1;
            for(int i=0;i<n;++i){
                if(state[i][m-1] !='*') continue;
    
                makeMove(state, i,turn);
                auto temp = minMax(state, depth -1, !turn, i);
                
                int k = getTopInColumn(state, i);
                state[i][k] = '*';

                if(temp.first > mx){
                    mx = temp.first;
                    mark = i;
                }
            }
            return {mx, mark};
        }
        else{
            int mn = 30000;
            int mark =-1;

            for(int i=0;i<n;++i){
                if(state[i][m-1] !='*') continue;
    
                makeMove(state, i,turn);
                auto temp = minMax(state, depth -1, !turn, i);
                
                int k = getTopInColumn(state, i);
                state[i][k] = '*';
                
                if(temp.first < mn){
                    mn = temp.first;
                    mark = i;
                }
            }
            return {mn, mark};
        }
    }
}


int main() {
    
    int input,depth;
    cout<<"Choose the depth of the search, it must be a number >=1\n";
    cin >> depth;
    
    while(depth <1){
        cout << "Invalid number. Choose the depth of the search, it must be a number >=1\n";
        cin >> depth;
    }

    cout << "Press 1 to start playing and 0 for the computer to start\n";
    cin >> input;

    while(input != 0 && input != 1){
        cout << "Invalid number. Press 1 to start playing and 0 for the computer to start\n";
        cin >> input;
    }

    bool turn = input;
    if(turn) player1 = false;
    else player1 = true;
    
    n = 7;
    m = 6;
    vector<vector<char>> state(n , vector<char> (m,'*'));
    bool tie;
    bool computerWon;
    int lastMove =-1;
    display(state);
    while(!gameIsOver(state, lastMove, tie, computerWon)){
        cout<<"\n";
        if(turn){ 
            cout<<"Choose a number from 1 to 7, according to the board below\n";
            display(state);
            int move;
            cin>> move;
            
            if(move > 7 || move < 1 || state[move -1][m-1] != '*' ){
                    while(move > 7 || move < 1 || state[move -1][m-1] != '*'){
                        if(move>7 || move<1)cout<<"Choose a number between 1 and 7 inclusive that is available\n";
                        else cout<<"This column is filed\n";
                    
                        display(state);
                        cin>>move;
                }
            }
            
            makeMove(state,move -1, turn);
            lastMove = move -1;
        }
        
        else{
            auto move = minMax(state, depth,turn, lastMove);
            makeMove(state,move.second, turn);
            lastMove = move.second;
        }

        turn = !turn;
    }


    if(tie){
        cout<<"The game is a tie\n";
        display(state);
    }
    else if(computerWon){
        cout<<"Better luck next time\n";
        display(state);

    }
    else{
        cout<<"Congratulations, you beat the machine\n";
        display(state);
    }

    return 0;
}