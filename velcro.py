#!/usr/bin/python2.6
import subprocess
import sys
import shlex
import select
#import sssssssBOOM
import nbt
import atexit
import curses
import curses.panel
import textwrap
import traceback

stdscr = None
input_win = None
seperator_win = None
server_proc = None
input_buffer = ""
main_wins = []
current_win = 0

def init_curses():
    global stdscr, input_win, seperator_win, main_wins
    stdscr = curses.initscr()
    stdscr.refresh()
    (height,width) = stdscr.getmaxyx()
    input_win = curses.newwin(1, width, height-1, 0)
    output_win = curses.newwin(height-2, width, 0, 0)
    output_panel = curses.panel.new_panel(output_win)
    main_wins.append(output_panel)
    seperator_win = curses.newwin(1, width, height-2, 0)
    output_win.scrollok(True)
    curses.noecho()
    curses.cbreak()
#curses.curs_set(1)
    stdscr.keypad(1)
    input_win.keypad(1)
    output_win.keypad(1)
    seperator_win.hline(curses.ACS_HLINE, width)
    seperator_win.refresh()
    input_win.echochar(ord('>'))
    input_win.echochar(ord(' '))
    input_win.nodelay(1)
    input_win.refresh()

def init_command_window():
    global main_wins, stdscr
    (height,width) = stdscr.getmaxyx()
    win = curses.newwin(height-2, width, 0, 0)
    win.scrollok(True)
    win.keypad(1)
    win.refresh()
    panel = curses.panel.new_panel(win)
    main_wins.append(panel)

@atexit.register
def clean_up():
    global server_proc
    reset_curses()
    if server_proc.poll() == None:
        server_proc.terminate()
    print "Minecraft closed, so let's shut down."

def reset_curses():
    global stdscr,input_win
    curses.nocbreak()
    stdscr.keypad(0)
    input_win.keypad(0)
    curses.echo()
    curses.endwin()

def display_output(line, win=None):
    global main_wins, current_win
    if win == None:
        window = main_wins[current_win].window()
    else:
        window = main_wins[win].window()
    (height,width) = window.getmaxyx()
    lines = textwrap.wrap(line, width)
    for eachline in lines:
        window.move(height-1,0)
        window.scroll()
        window.insstr(eachline)
    if win == None or current_win == win:
        window.refresh()

def retrieve_input():
    global input_win, input_buffer, current_win, main_wins
    while True:
        char = input_win.getch()
        if char == -1:
            break
        if char <= 128:
            input_buffer += chr(char)
            if char == ord('\n'):
                input_win.deleteln()
                input_win.move(0,0)
                input_win.echochar(ord('>'))
                input_win.echochar(ord(' '))
                retstr = input_buffer
                input_buffer = ""
                return retstr
            else:
                input_win.echochar(char)
        else:
            # it's a control signal or somesuch!
            if char == curses.KEY_RESIZE:
                init_curses()
            elif char == curses.KEY_RIGHT:
                current_win = (current_win+1)%len(main_wins)
                main_wins[current_win].top()
                curses.panel.update_panels()
                curses.doupdate()
            return

def get_command(line):
    line = line.split()
    if len(line) > 3:
        player = line[3].strip('<>')
        command = ' '.join(line[4:])
    else:
        player = None
        command = None
    return (player, command)

def find_loc(Player, map_location):
    nbt_filename = "%s/players/%s.dat" % (map_location, Player)
    nbt_file = nbt.NBTFile(nbt_filename, 'rb')
    (x,z,y) = nbt_file["Pos"].tags
    return "say %d %d %d" % (x.value,y.value,z.value)

def run():
    global server_proc, stdscr
    init_curses()
    mem = "1024M"
    server_command = "java -Xmx%s -Xms%s -jar minecraft_server.jar nogui" % (mem,mem)
# grab this from the server.properties, yeah?
    map_location = "/home/landon/Desktop/mcbackupserver/unknown"
    args = shlex.split(server_command)
    server_proc = subprocess.Popen(args, \
            stdin=subprocess.PIPE, \
            stdout=subprocess.PIPE, \
            stderr=subprocess.PIPE)

    console_input = sys.stdin
    cmd_queue = []
    init_command_window()

    while server_proc.poll() == None:
        (rlist, wlist, xlist) = select.select( \
                [server_proc.stdout, server_proc.stderr], \
                [server_proc.stdin,], \
                [], .1)

        console_input = retrieve_input()
        if console_input:
            display_output(console_input)
            if current_win == 0:
                cmd_queue.append(console_input)

        for r in rlist:
            line = r.readline().strip()
            if r == server_proc.stdout or r == server_proc.stderr:
                if len(line) > 0:
                    display_output(line, 0)
#print line
                    (player, player_cmd) = get_command(line)
                    if player_cmd:
                        # 2011-02-28 14:02:31 [INFO] <TensaiRonin> lol it mapped a world hole
                        if player_cmd == "loc":
                            loc = find_loc(player, map_location)
                            cmd_queue.append("say %s") % loc
        for w in wlist:
            if w == server_proc.stdin:
                if (len(cmd_queue) > 0):
                    command = cmd_queue.pop(0)
                    w.write("%s" % command)

        stdscr.refresh()


if __name__ == "__main__":
    run()
