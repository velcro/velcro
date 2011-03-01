#!/usr/bin/python2.6
import subprocess
import sys
import shlex
import select
#import sssssssBOOM
import nbt
import atexit
import curses
import textwrap
import traceback

stdscr = None
output_win = None
input_win = None
seperator_win = None
server_proc = None
input_buffer = ""

def init_curses():
    global stdscr, output_win, input_win, seperator_win
    stdscr = curses.initscr()
    stdscr.refresh()
    (height,width) = stdscr.getmaxyx()
    input_win = curses.newwin(1, width, height-1, 0)
    output_win = curses.newwin(height-2, width, 0, 0)
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

@atexit.register
def clean_up():
    global server_proc
    reset_curses()
    if server_proc.poll() != None:
        server_proc.terminate()

def reset_curses():
    global stdscr
    curses.nocbreak()
    stdscr.keypad(0)
    input_win.keypad(0)
    output_win.keypad(0)
    curses.echo()
    curses.endwin()

def display_output(line):
    global output_win
    (height,width) = output_win.getmaxyx()
    lines = textwrap.wrap(line, width)
    for eachline in lines:
        output_win.move(height-1,0)
        output_win.scroll()
        output_win.insstr(eachline)
    output_win.refresh()

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
    global server_proc
    global stdscr
    global input_win
    global output_win
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

    while server_proc.poll() == None:
        (rlist, wlist, xlist) = select.select( \
                [server_proc.stdout, server_proc.stderr], \
                [server_proc.stdin,], \
                [], .1)

        console_input = retrieve_input()
        if console_input:
            display_output(console_input)

        for r in rlist:
            line = r.readline().strip()
            if r == server_proc.stdout or r == server_proc.stderr:
                if len(line) > 0:
                    display_output(line)
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
                    w.write("%s\n" % command)

        stdscr.refresh()


    print "Minecraft closed, so let's shut down."

if __name__ == "__main__":
    run()
