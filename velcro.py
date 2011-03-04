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
import time
import os
import os.path
import shutil
import signal

# grab this from the server.properties, yeah?
map_location = "/home/landon/Desktop/mcbackupserver/"
map_name = "unknown/"
num_backups = 5
backup_period = 10
output_buffer_len = 100
mem = "1024M"

#Don't change anything below this line

server_proc = None
interrupts = 0

class gui:
    def __init__(self, output_buffer_len=100, buffers={}, current=0, players=0, input_buffer=""):
        self.input_buffer = input_buffer
        self.players = players
        self.output_buffer_len = output_buffer_len
        self.buffers = buffers
        self.windows = {}
        self.window_order = []
        self.current_window = current
        self.stdscr = curses.initscr()
        (self.height, self.width) = self.stdscr.getmaxyx()
        self.colors = {}
        self.init_colors()
        self.init_windows()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        self.stdscr.keypad(1)

    def init_colors(self):
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_YELLOW, -1)
        curses.init_pair(2, curses.COLOR_CYAN, -1)
        curses.init_pair(3, curses.COLOR_RED, -1)
        curses.init_pair(4, curses.COLOR_GREEN, -1)
        curses.init_pair(5, curses.COLOR_MAGENTA, -1)
        self.colors['warning'] = 1
        self.colors['info'] = 2
        self.colors['error'] = 3
        self.colors['chat'] = 4
        self.colors['player'] = 5

    def init_windows(self):
        self.window_order = ["Minecraft Server", "Players", "Messages", "Warnings", "Errors", "Backups", "Mapping"]
        for win_name in self.window_order:
            self.init_main_window(win_name)
        self.windows["Minecraft Server"].top()
        # Keep this above the input_win and separator_win, otherwise it destroys them when called the first time
        curses.panel.update_panels()

        self.separator_win = curses.newwin(1, self.width, self.height-2, 0)
        self.display_window_name()

        self.input_win = curses.newwin(1, self.width, self.height-1, 0)
        self.input_win.keypad(1)
        self.input_win.nodelay(1)
        self.input_win.echochar(ord('>'))
        self.input_win.echochar(ord(' '))

        self.windows[self.window_order[self.current_window]].window().refresh()

    def init_main_window(self, window_name):
        window = curses.newwin(self.height-2, self.width, 0, 0)
        if window_name in self.windows:
            self.windows[window_name].replace(window)
        else:
            panel = curses.panel.new_panel(window)
            self.windows[window_name] = panel
        window.scrollok(True)
        window.keypad(1)
        if window_name not in self.buffers:
            self.buffers[window_name] = []
        else:
            self.display_buffer(window_name)

    def display_buffer(self, buffer_name):
        printed = 0
        for line in self.buffers[buffer_name][-self.height:]:
            wrapped_lines = textwrap.wrap(line[0], self.width)
            for wrapped_line in wrapped_lines:
                self.display(wrapped_line, win_name=buffer_name, color=line[1], buffer_line=False)
                printed += 1
            if printed > self.height:
                break

    def display_window_name(self, name=None, players=None):
        if name == None:
            name = self.window_order[self.current_window]
        name_str = name+" |"
        brand_str = "| Velcro"
        if players != None:
            self.players = players
        player_str= "| %d players " % self.players
        info_str = player_str+brand_str
        if self.width > len(info_str)+len(name_str):
            self.separator_win.move(0,0)
            self.separator_win.insstr(name_str)
            self.separator_win.move(0, self.width-len(info_str))
            self.separator_win.insstr(info_str)
            if (self.width-len(name_str)-len(info_str)) > 0:
                self.separator_win.move(0, len(name_str))
                self.separator_win.hline(curses.ACS_HLINE, self.width-len(name_str)-len(info_str))
        self.separator_win.refresh()

    def display(self, text, win_name=None, color=None, buffer_line=True):
        if win_name == None:
            win_name = self.window_order[self.current_window]
        window = self.windows[win_name].window()
        (height, width) = window.getmaxyx()
        lines = textwrap.wrap(text, width)
        for line in lines:
            window.move(height-1, 0)
            window.scroll()
            if color == None:
                window.insstr(line)
            else:
                color_id = self.colors[color]
                window.insstr(line, curses.color_pair(color_id))
        if win_name == self.window_order[self.current_window]:
            window.refresh()
        if buffer_line:
            text_pair = (text, color)
            if len(self.buffers[win_name]) > self.output_buffer_len:
                self.buffers[win_name].pop(0)
            self.buffers[win_name].append(text_pair)

    def retrieve_input(self):
        while True:
            char = self.input_win.getch()
            if char == -1:
                break
            elif char <= 128:
                if char == ord('\n'):
                    self.input_win.deleteln()
                    self.input_win.move(0,0)
                    self.input_win.echochar(ord('>'))
                    self.input_win.echochar(ord(' '))
                    retstr = self.input_buffer
                    self.input_buffer = ""
                    return retstr
                else:
                    self.input_buffer += chr(char)
                    self.input_win.echochar(char)
            elif char == curses.KEY_BACKSPACE:
                (y,x) = self.input_win.getyx()
                self.input_buffer = self.input_buffer[:-1]
                if x>2:
                    self.input_win.move(y,x-1)
                    self.input_win.delch(y,x-1)
            else:
                # It's a control signal!
                self.control_input(char)

    def control_input(self, char):
        if char == curses.KEY_RESIZE:
            self.__init__(self.output_buffer_len, self.buffers, self.current_window, self.players, self.input_buffer)
        elif char == curses.KEY_RIGHT or char == curses.KEY_LEFT:
            direction = 1
            if char == curses.KEY_LEFT:
                direction = -1
            self.current_window = (self.current_window+direction)%len(self.window_order)
            self.display_window_name(self.window_order[self.current_window])
            self.windows[self.window_order[self.current_window]].top()
            curses.panel.update_panels()
            curses.panel.top_panel().window().refresh()
            curses.doupdate()

class server_helpers:
    cmd_queue = []
    warning_re = re.compile(r'(?P<message>\S+ \S+ \[WARNING\] .*)')
    logins_re = re.compile(r'(?P<message>\S+ \S+ \[INFO\] ((?P<player>\S+) (\[[^\]]+\] logged in with entity id \d+|lost connection: (?P<disconnect>.*))))')
    chat_re = re.compile(r'(?P<message>\S+ \S+ \[INFO\] (?P<name>\[CONSOLE\]|\<\S+\>) (?P<chat>.*))')
    PM_re = re.compile(r'(?P<message>\S+ \S+ \[INFO\] (?P<from>\S+)[^: ] (.*) to (?P<to>\S+))')
    java_re = re.compile(r'(?P<error>(?:java|at) .*)')
    save_re = re.compile(r'(?P<message>\S+ \S+ \[INFO\] CONSOLE: Save complete\.)')
    saved = False
    saving = False
    gui = None
    players = []

    @staticmethod
    def parse_line(line):
        match = server_helpers.chat_re.match(line)
        if match:
            message = match.group('message')
            chat_message = match.group('chat')
            name = match.group('name').strip("<>[]")
            if not name == "CONSOLE":
                server_helpers.player_cmd(name, chat_message)
            server_helpers.gui.display(message, win_name="Messages", color="chat")
            return
        match = server_helpers.PM_re.match(line)
        if match:
            message = match.group('message')
            server_helpers.gui.display(message, win_name="Messages", color="chat")
            return
        match = server_helpers.logins_re.match(line)
        if match:
            message = match.group('message')
            playername = match.group('player')
            if playername in server_helpers.players:
                server_helpers.players.remove(playername)
            else:
                server_helpers.players.append(playername)
            server_helpers.gui.display_window_name(players=len(server_helpers.players))
            server_helpers.gui.display(message, win_name="Players", color="player")
            server_helpers.gui.display(message, win_name="Messages", color="player")
            return
        match = server_helpers.warning_re.match(line)
        if match:
            message = match.group('message')
            server_helpers.gui.display(message, win_name="Warnings", color="warning")
            server_helpers.gui.display(message, win_name="Minecraft Server", color="warning")
            return
        match = server_helpers.java_re.match(line)
        if match:
            message = match.group('error')
            server_helpers.gui.display(message, win_name="Errors", color="error")
            server_helpers.gui.display(message, win_name="Minecraft Server", color="error")
            return
        match = server_helpers.save_re.match(line)
        if match:
            server_helpers.saved = True
            server_helpers.saving = False
        server_helpers.gui.display(line, win_name="Minecraft Server", color="info")
        line = line.split()

    @staticmethod
    def player_cmd(player, message):
        tokens = message.split()
        if tokens[0] == "!login_loc":
            server_helpers.add_to_queue(server_helpers.find_loc(player, map_location))
        elif tokens[0] == "!list":
            playerstr = ' '.join(server_helpers.players)
            playerstr = "say Currently on: "+playerstr
            server_helpers.add_to_queue(playerstr)

    @staticmethod
    def find_loc(Player, map_location):
        nbt_filename = "%s%s/players/%s.dat" % (map_location, map_name, Player)
        nbt_file = nbt.NBTFile(nbt_filename, 'rb')
        (x,z,y) = nbt_file["Pos"].tags
        return "say %d %d %d" % (x.value,y.value,z.value)

    @staticmethod
    def add_to_queue(command):
        server_helpers.cmd_queue.append("%s\n" % command)

    @staticmethod
    def save():
        if not server_helpers.saving and not server_helpers.saved:
            server_helpers.add_to_queue("save-off")
            server_helpers.add_to_queue("save-all")
            server_helpers.saving = True
        else:
            return server_helpers.saved

class backup_helpers:
    backup_dir = "%s/velcro/backups/%s/" % (map_location, map_name)
    backup_command = "rsync -av --delete --link-dest=%s %s %s" % ("%s", "%s%s" % (map_location, map_name), "%s/")
    first_backup_command = "rsync -av %s %s" % ("%s%s" % (map_location, map_name), "%s/")
    backup_process = None
    in_progress = False
    time_last_backup = time.time()
    color = 0
    gui = None

    @staticmethod
    def start_backup():
        backup_helpers.color = (backup_helpers.color+1)%len(backup_helpers.gui.colors)
        backup_helpers.in_progress = True
        backup_helpers.gui.display("Starting backups for %s" % time.strftime("%Y/%m/%d %H:%M:%S"), win_name="Backups", color=backup_helpers.get_color())
        linkdest = backup_helpers.get_most_recent()
        linkdest_path = "%s%s" % (backup_helpers.backup_dir, linkdest)
        new_backup_dir = "%s%s" % (backup_helpers.backup_dir, time.strftime("%Y-%m-%d.%H-%M-%S"))
        if linkdest == None:
            args = shlex.split(backup_helpers.first_backup_command % (new_backup_dir))
            backup_helpers.gui.display(backup_helpers.first_backup_command % (new_backup_dir), win_name="Backups", color=backup_helpers.get_color())
        else:
            args = shlex.split(backup_helpers.backup_command % (linkdest_path, new_backup_dir))
            backup_helpers.gui.display(backup_helpers.backup_command % (linkdest_path, new_backup_dir), win_name="Backups", color=backup_helpers.get_color())
        backup_helpers.backup_process = subprocess.Popen(args, \
            stdout=subprocess.PIPE, \
            stderr=subprocess.PIPE)
        backup_helpers.trim_backups()

    @staticmethod
    def get_most_recent():
        backups = os.listdir(backup_helpers.backup_dir)
        if len(backups) == 0:
            return None
        else:
            backups.sort()
            return backups.pop()

    @staticmethod
    def get_least_recent():
        least_recent = []
        backups = os.listdir(backup_helpers.backup_dir)
        backups.sort()
        while len(backups) > num_backups:
            least_recent.append(backups.pop(0))
        return least_recent

    @staticmethod
    def trim_backups():
        to_prune = backup_helpers.get_least_recent()
        for backup in to_prune:
            backup_path = "%s%s" % (backup_helpers.backup_dir, backup)
            shutil.rmtree(backup_path, True)

    @staticmethod
    def get_color():
        return backup_helpers.gui.colors.keys()[backup_helpers.color]

def graceful_exit(signum, frame):
    global interrupts
    if interrupts > 0:
        sys.exit(0)
    else:
        server_helpers.add_to_queue("stop")
    interrupts += 1


@atexit.register
def clean_up():
    global server_proc
    curses.nocbreak()
    curses.echo()
    curses.endwin()
    try:
        traceback.print_last()
    except:
        pass
    if server_proc.poll() == None:
        server_proc.terminate()
    print "Minecraft closed, so let's shut down."

def check_directories():
    if not os.path.exists("%s/velcro/backups/%s" % (map_location, map_name)):
        os.makedirs("%s/velcro/backups/%s" % (map_location, map_name))

def run():
    global server_proc, map_location, mem, players
    check_directories()
    curses_gui = gui()
    backup_helpers.gui = curses_gui
    server_helpers.gui = curses_gui
    server_command = "java -Xmx%s -Xms%s -jar minecraft_server.jar nogui" % (mem,mem)
    args = shlex.split(server_command)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    server_proc = subprocess.Popen(args, \
            stdin=subprocess.PIPE, \
            stdout=subprocess.PIPE, \
            stderr=subprocess.PIPE)
    signal.signal(signal.SIGINT, graceful_exit)

    while server_proc.poll() == None:
        read_list = [server_proc.stdout, server_proc.stderr, sys.stdin]
        if backup_helpers.backup_process != None:
            read_list.append(backup_helpers.backup_process.stdout)
            read_list.append(backup_helpers.backup_process.stderr)
        try:
            (rlist, wlist, xlist) = select.select( \
                    read_list, \
                    [], \
# Seems to be why we take up 99% CPU so let's assume it's always ready
#                [server_proc.stdin,], \
                    [], .1)
        except:
            continue

        console_input = curses_gui.retrieve_input()
        if console_input:
            curses_gui.display(console_input)
            if console_input[0] != "!":
                if curses_gui.current_window == curses_gui.window_order.index("Messages"):
                    server_helpers.add_to_queue("say %s" % console_input)
                elif curses_gui.current_window == curses_gui.window_order.index("Minecraft Server"):
                    server_helpers.add_to_queue(console_input)
            else:
                if console_input == "!list":
                    curses_gui.display("Currently on: " + ' '.join(server_helpers.players), color='player')

        for r in rlist:
            if r == server_proc.stdout or r == server_proc.stderr:
                line = r.readline().strip()
                if len(line) > 0:
                    server_helpers.parse_line(line)
            elif backup_helpers.backup_process != None:
                if r == backup_helpers.backup_process.stdout or r == backup_helpers.backup_process.stderr:
                    line = r.readline().strip()
                    if len(line) > 0:
                        curses_gui.display(line, win_name="Backups", color = backup_helpers.get_color())

        if (len(server_helpers.cmd_queue) > 0):
            server_proc.stdin.writelines(server_helpers.cmd_queue)
            server_helpers.cmd_queue = []

        if (time.time()-backup_helpers.time_last_backup) > backup_period and not backup_helpers.in_progress:
            continue_backup = server_helpers.save()
            if continue_backup:
                server_helpers.add_to_queue("say Starting backups!")
                backup_helpers.start_backup()
        elif backup_helpers.in_progress and server_helpers.saved:
            if backup_helpers.backup_process.poll() != None:
                server_helpers.saved = False
                backup_helpers.in_progress = False
                backup_helpers.time_last_backup = time.time()
                backup_helpers.backup_process = None
                server_helpers.add_to_queue("save-on")
                server_helpers.add_to_queue("say Backups over!")


if __name__ == "__main__":
    run()
