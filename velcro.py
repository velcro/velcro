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
command_char = "!"

#Don't change anything below this line
server_global = None


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

class MinecraftServer:
    server_command = "java -Xmx%s -Xms%s -jar minecraft_server.jar nogui" % (mem,mem)
    cmd_queue = []
    save_state = None
    process = None
    players = []

    # Message parsing regexen
    warning_re = re.compile(r'(?P<message>\S+ \S+ \[WARNING\] .*)')
    login_re = re.compile(r'(?P<message>\S+ \S+ \[INFO\] (?P<player>\S+) (\[[^\]]+\] logged in with entity id \d+))')
    logout_re = re.compile(r'(?P<message>\S+ \S+ \[INFO\] lost connection: (?P<disconnect>.*))')
    chat_re = re.compile(r'(?P<message>\S+ \S+ \[INFO\] (?P<name>\[CONSOLE\]|\<\S+\>) (?P<chat>.*))')
    PM_re = re.compile(r'(?P<message>\S+ \S+ \[INFO\] (?P<from>\S+)[^: ] (.*) to (?P<to>\S+))')
    java_re = re.compile(r'(?P<error>(?:java|at |\S+ \S+ \[SEVERE\]).*)')
    save_re = re.compile(r'(?P<message>\S+ \S+ \[INFO\] CONSOLE: Save complete\.)')

    def __init__(self, gui):
        self.gui = gui
        self.start()

    def start(self):
        args = shlex.split(self.server_command)
        self.process = subprocess.Popen(args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
        self.stdin = self.process.stdin
        self.stderr = self.process.stderr
        self.stdout = self.process.stdout

    def running(self):
        if self.process == None:
            return False
        if self.process.poll() == None:
            return True
        return False

    def force_save(self):
        if self.save_state ==  None:
            self.add_to_queue("save-off")
            self.add_to_queue("save-all")
            self.save_state = "saving"

    def autosave(self):
        self.add_to_queue("save-on")
        self.save_state = None

    def saved(self):
        return self.save_state == "saved"

    def saving(self):
        return self.save_state == "saving"

    def parse_line(self, line):
        global command_char
        match = self.chat_re.match(line)
        if match:
            message = match.group('message')
            chat_message = match.group('chat')
            name = match.group('name').strip("<>[]")
            if not name == "CONSOLE" and chat_message[0] == command_char:
                self.player_cmd(name, chat_message)
            self.gui.display(message, win_name="Messages", color="chat")
            return
        match = self.PM_re.match(line)
        if match:
            message = match.group('message')
            self.gui.display(message, win_name="Messages", color="chat")
            return
        login_match = self.login_re.match(line)
        logout_match = self.logout_re.match(line)
        if login_match:
            message = login_match.group('message')
            playername = login_match.group('player')
            self.players.append(playername)
        if logout_match:
            message = logout_match.group('message')
            playername = logout_match.group('player')
            self.players.remove(playername)
        if login_match or logout_match:
            self.gui.display_window_name(players=len(self.players))
            self.gui.display(message, win_name="Players", color="player")
            self.gui.display(message, win_name="Messages", color="player")
            return
        match = self.warning_re.match(line)
        if match:
            message = match.group('message')
            self.gui.display(message, win_name="Warnings", color="warning")
            self.gui.display(message, win_name="Minecraft Server", color="warning")
            return
        match = self.java_re.match(line)
        if match:
            message = match.group('error')
            self.gui.display(message, win_name="Errors", color="error")
            self.gui.display(message, win_name="Minecraft Server", color="error")
            return
        match = self.save_re.match(line)
        if match:
            self.save_state = "saved"
        self.gui.display(line, win_name="Minecraft Server", color="info")

    def player_cmd(self, player, message):
        tokens = message.split()
        command = tokens[0][1:]
        if command == "login_loc":
            self.say("%d %d %d" % self.find_loc(player))
        elif command == "list":
            self.say(self.list_players(), player)

    def list_players(self):
        playerstr = "Currently on: " + ', '.join(self.players)
        return playerstr

    def say(self, message, player=None):
        if player:
            self.private_msg(message, player)
            return
        self.add_to_queue("say %s" % message)

    def private_msg(self, message, player):
        self.add_to_queue("tell %s %s" % (player, message))

    def add_to_queue(self, command):
        self.cmd_queue.append("%s\n" % command)

    def send_commands(self):
        if len(self.cmd_queue) > 0:
            self.stdin.writelines(self.cmd_queue)
            self.cmd_queue = []

    def find_loc(self, player):
        global map_location, map_name
        nbt_filename = "%s%s/players/%s.dat" % (map_location, map_name, player)
        nbt_file = nbt.NBTFile(nbt_filename, 'rb')
        (x,z,y) = nbt_file["Pos"].tags
        return (x.value,y.value,z.value)

class Backup:
    backup_dir = "%s/velcro/backups/%s/" % (map_location, map_name)
    backup_command = "rsync -av --delete --link-dest=%s %s %s" % ("%s", map_location+map_name, "%s/")
    initial_backup_command = "rsync -av %s %s" % (map_location+map_name, "%s/")
    color = 0
    last_backup = time.time()
    gui = None
    process = None

    def __init__(self, gui, num_backups):
        self.num_backups = num_backups
        self.gui = gui
        self.gui.display("Running initial backup for %s" % time.strftime("%Y/%m/%d %H:%M:%S"), win_name="Backups", color=self.get_color(1))
        self.start()

    def start(self):
        self.color = (self.color+1)%len(self.gui.colors)
        self.gui.display("Starting backups for %s" % time.strftime("%Y/%m/%d %H:%M:%S"), win_name="Backups", color=self.get_color())
        linkdest = self.get_most_recent()
        new_backup_dir = self.backup_dir + time.strftime("%Y-%m-%d.%H-%M-%S")
        if linkdest == None:
            args = shlex.split(self.initial_backup_command % new_backup_dir)
            self.gui.display(self.initial_backup_command % new_backup_dir, win_name="Backups", color=self.get_color())
        else:
            linkdest = self.get_most_recent()
            linkdest_path = self.backup_dir + linkdest
            args = shlex.split(self.backup_command % (linkdest_path, new_backup_dir))
            self.gui.display(self.backup_command  % (linkdest_path, new_backup_dir), win_name="Backups", color=self.get_color())

        self.process = subprocess.Popen(args, \
                stdout=subprocess.PIPE, \
                stderr=subprocess.PIPE)

        self.stdout = self.process.stdout
        self.stderr = self.process.stderr
        self.trim_backups()

    def finish(self):
        self.process = None
        self.last_backup = time.time()

    def running(self):
        if self.process == None:
            return False
        if self.process.poll() == None:
            return True
        return False

    def get_most_recent(self):
        backups = os.listdir(self.backup_dir)
        if len(backups) == 0:
            return None
        else:
            backups.sort()
            return backups.pop()

    def get_least_recent(self):
        least_recent = []
        backups = os.listdir(self.backup_dir)
        backups.sort()
        while len(backups) > self.num_backups:
            least_recent.append(backups.pop(0))
        return least_recent

    def trim_backups(self):
        to_prune = self.get_least_recent()
        for backup in to_prune:
            backup_path = self.backup_dir+backup
            shutil.rmtree(backup_path, True)

    def get_color(self, color=None):
        if color == None:
            return self.gui.colors.keys()[self.color]
        else:
            return self.gui.colors.keys()[color]

def graceful_exit(signum, frame):
    global server_global
    if server_global:
        server_global.add_to_queue("stop")
    else:
        sys.exit(0)


@atexit.register
def clean_up():
    global server_global
    curses.nocbreak()
    curses.echo()
    curses.endwin()
    try:
        traceback.print_last()
    except:
        pass
    if server_global:
        if server_global.running() == None:
            server_global.process.terminate()
    print "Minecraft closed, so let's shut down."

def check_directories():
    if not os.path.exists("%s/velcro/backups/%s" % (map_location, map_name)):
        os.makedirs("%s/velcro/backups/%s" % (map_location, map_name))

def run():
    global map_location, map_name, mem, players, server_global, command_char, num_backups
    check_directories()
    curses_gui = gui()

    # Ignore before staring up the server so SIGINT is only handled by this script
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    server = MinecraftServer(curses_gui)
    signal.signal(signal.SIGINT, graceful_exit)
    server_global = server

    backup = Backup(curses_gui, num_backups)

    while server.running():
        read_list = [server.stdout, server.stderr, sys.stdin]
        if backup.running():
            read_list.append(backup.stdout)
            read_list.append(backup.stderr)
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
            if console_input[0] != command_char:
                if curses_gui.current_window == curses_gui.window_order.index("Messages"):
                    server.say(console_input)
                elif curses_gui.current_window == curses_gui.window_order.index("Minecraft Server"):
                    server.add_to_queue(console_input)
            else:
                if console_input[1:] == "list":
                    curses_gui.display(server.list_players(), color='player')

        for r in rlist:
            if r == server.stdout or r == server.stderr:
                line = r.readline().strip()
                if len(line) > 0:
                    server.parse_line(line)
            elif backup.running():
                if r == backup.stdout or r == backup.stderr:
                    line = r.readline().strip()
                    if len(line) > 0:
                        curses_gui.display(line, win_name="Backups", color = backup.get_color())

        server.send_commands()

        if not backup.running():
            if server.saved():
                server.autosave()
                server.say("Backups over!")
                backup.finish()
            elif (time.time()-backup.last_backup) > backup_period:
                # implied not server.saved()
                if not server.saving():
                    server.force_save()
                    server.say("Starting backups!")
                    backup.start()

if __name__ == "__main__":
    run()
