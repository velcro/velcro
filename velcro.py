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
import re

# grab this from the server.properties, yeah?
map_location = "/home/landon/Desktop/mcbackupserver/unknown"
mem = "1024M"

#Don't change anything below this line

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
        curses_helpers.init_command_window("Players")
        curses_helpers.init_command_window("Messages")
        curses_helpers.init_command_window("Warnings")
        curses_helpers.init_command_window("Errors")
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
    def display_output(line, win=None, win_name=None):
        global main_wins, main_names, current_win
        if win_name != None:
            win = main_names.index(win_name)
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
        if current_win == win:
            window.refresh()

    @staticmethod
    def retrieve_input():
        global input_win, input_buffer
        while True:
            char = input_win.getch()
            if char == -1:
                break
            if char <= 128:
                if char == ord('\n'):
                    input_win.deleteln()
                    input_win.move(0,0)
                    input_win.echochar(ord('>'))
                    input_win.echochar(ord(' '))
                    retstr = input_buffer
                    input_buffer = ""
                    return retstr
                else:
                    input_buffer += chr(char)
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

class server_helpers:
    cmd_queue = []
    warning_re = re.compile(r'(?P<message>\S+ \S+ \[WARNING\] .*)')
    logins_re = re.compile(r'(?P<message>\S+ \S+ \[INFO\] (\S+ (\[[^]]+\] logged in with entity id \d+|lost connection: (?P<disconnect>.*))|Connected players: (?P<players>.*)))')
    chat_re = re.compile(r'(?P<message>\S+ \S+ \[INFO\] (?P<name>\[CONSOLE\]|\<\S+\>) (?P<chat>.*))')
    PM_re = re.compile(r'(?P<message>\S+ \S+ \[INFO\] (?P<from>\S+) (.*) to (?P<to>\S+))')
    java_re = re.compile(r'(?P<error>(?:java|at) .*)')

    @staticmethod
    def parse_line(line):
        match = server_helpers.chat_re.match(line)
        if match:
            message = match.group('message')
            chat_message = match.group('chat')
            name = match.group('name').strip("<>[]")
            if not name == "CONSOLE":
                server_helpers.player_cmd(name, chat_message)
            curses_helpers.display_output(message, win_name="Messages")
            return
        match = server_helpers.PM_re.match(line)
        if match:
            message = match.group('message')
            curses_helpers.display_output(message, win_name="Messages")
            return
        match = server_helpers.logins_re.match(line)
        if match:
            message = match.group('message')
            curses_helpers.display_output(message, win_name="Players")
            return
        match = server_helpers.warning_re.match(line)
        if match:
            message = match.group('message')
            curses_helpers.display_output(message, win_name="Warnings")
            curses_helpers.display_output(message, win_name="Minecraft Server")
            return
        match = server_helpers.java_re.match(line)
        if match:
            message = match.group('message')
            curses_helpers.display_output(message, win_name="Errors")
            curses_helpers.display_output(message, win_name="Minecraft Server")
            return
        else:
            curses_helpers.display_output(line, win_name="Minecraft Server")
        line = line.split()

    @staticmethod
    def player_cmd(player, message):
        tokens = message.split()
        if tokens[0] == "loc":
            server_helpers.add_to_queue(server_helpers.find_loc(player, map_location))

    @staticmethod
    def find_loc(Player, map_location):
        nbt_filename = "%s/players/%s.dat" % (map_location, Player)
        nbt_file = nbt.NBTFile(nbt_filename, 'rb')
        (x,z,y) = nbt_file["Pos"].tags
        return "say %d %d %d" % (x.value,y.value,z.value)

    @staticmethod
    def add_to_queue(command):
        server_helpers.cmd_queue.append("%s\n" % command)

@atexit.register
def clean_up():
    global server_proc
    curses_helpers.reset_curses()
    try:
        traceback.print_last()
    except:
        pass
    if server_proc.poll() == None:
        server_proc.terminate()
    print "Minecraft closed, so let's shut down."

def run():
    global server_proc, map_location, mem
    curses_helpers.init_curses()
    server_command = "java -Xmx%s -Xms%s -jar minecraft_server.jar nogui" % (mem,mem)
    args = shlex.split(server_command)
    server_proc = subprocess.Popen(args, \
            stdin=subprocess.PIPE, \
            stdout=subprocess.PIPE, \
            stderr=subprocess.PIPE)

    while server_proc.poll() == None:
        (rlist, wlist, xlist) = select.select( \
                [server_proc.stdout, server_proc.stderr, sys.stdin], \
                [], \
# Seems to be why we take up 99% CPU so let's assume it's always ready
#                [server_proc.stdin,], \
                [])

        console_input = curses_helpers.retrieve_input()
        if console_input:
            curses_helpers.display_output(console_input)
            if current_win == main_names.index("Minecraft Server"):
                server_helpers.add_to_queue(console_input)
            elif current_win == main_names.index("Messages"):
                server_helpers.add_to_queue("say %s" % console_input)

        for r in rlist:
            if r == server_proc.stdout or r == server_proc.stderr:
                line = r.readline().strip()
                if len(line) > 0:
                    server_helpers.parse_line(line)

        if (len(server_helpers.cmd_queue) > 0):
            server_proc.stdin.writelines(server_helpers.cmd_queue)
            server_helpers.cmd_queue = []


if __name__ == "__main__":
    run()
