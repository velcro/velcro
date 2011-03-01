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
separator_win = None
server_proc = None
input_buffer = ""
main_wins = []
main_names = []
current_win = 0

class curses_helpers:
    @staticmethod
    def init_curses():
        global stdscr, input_win, separator_win, main_wins, current_win
        stdscr = curses.initscr()
        stdscr.refresh()
        (height,width) = stdscr.getmaxyx()
        input_win = curses.newwin(1, width, height-1, 0)
        curses_helpers.init_command_window("Minecraft Server")
        curses_helpers.init_command_window("CONSOLE")
        curses_helpers.init_command_window("Messages")
        curses_helpers.init_command_window("Private Messages")
        curses_helpers.init_command_window("Warnings")
        separator_win = curses.newwin(1, width, height-2, 0)
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        stdscr.keypad(1)
        input_win.keypad(1)
        curses_helpers.display_window_name(main_names[current_win])
        separator_win.refresh()
        input_win.echochar(ord('>'))
        input_win.echochar(ord(' '))
        input_win.nodelay(1)

    @staticmethod
    def init_command_window(name):
        global main_wins, stdscr
        (height,width) = stdscr.getmaxyx()
        win = curses.newwin(height-2, width, 0, 0)
        win.scrollok(True)
        win.keypad(1)
        win.refresh()
        panel = curses.panel.new_panel(win)
        main_wins.append(panel)
        main_names.append(name)

    @staticmethod
    def display_window_name(name):
        global separator_win
        name = name+" |"
        (height, width) = separator_win.getmaxyx()
        separator_win.move(0,0)
        separator_win.insstr(name)
        separator_win.move(0,len(name))
        separator_win.hline(curses.ACS_HLINE, width-len(name))
        separator_win.refresh()

    @staticmethod
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

    @staticmethod
    def retrieve_input():
        global input_win, input_buffer
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
                curses_helpers.control_input(char)


    @staticmethod
    def control_input(char):
        global current_win, main_wins, main_names
        if char == curses.KEY_RESIZE:
            init_curses()
        elif char == curses.KEY_RIGHT or char == curses.KEY_UP or char == curses.KEY_LEFT or char == curses.KEY_DOWN:
            direction = 1
            if char == curses.KEY_LEFT or char == curses.KEY_DOWN:
                direction = -1
            current_win = (current_win+direction)%len(main_wins)
            curses_helpers.display_window_name(main_names[current_win])
            main_wins[current_win].top()
            curses.panel.update_panels()
            main_wins[current_win].window().refresh()
            curses.doupdate()

    @staticmethod
    def reset_curses():
        global stdscr,input_win
        curses.nocbreak()
        stdscr.keypad(0)
        input_win.keypad(0)
        curses.echo()
        curses.endwin()


@atexit.register
def clean_up():
    global server_proc
    curses_helpers.reset_curses()
    traceback.print_last()
    if server_proc.poll() == None:
        server_proc.terminate()
    print "Minecraft closed, so let's shut down."

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
    curses_helpers.init_curses()
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

    while server_proc.poll() == None:
        (rlist, wlist, xlist) = select.select( \
                [server_proc.stdout, server_proc.stderr], \
                [server_proc.stdin,], \
                [], .01)

        console_input = curses_helpers.retrieve_input()
        if console_input:
            curses_helpers.display_output(console_input)
            if current_win == 0:
                cmd_queue.append(console_input)

        for r in rlist:
            line = r.readline().strip()
            if r == server_proc.stdout or r == server_proc.stderr:
                if len(line) > 0:
                    curses_helpers.display_output(line, 0)
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



if __name__ == "__main__":
    run()
