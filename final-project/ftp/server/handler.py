from random import randint
from threading import Thread
from typing import Callable, List, Optional
from utils import Path, Reply, Socket
import os
import socket
import time


class DataHandler(Thread):
  def __init__(self, data_socket: socket.socket):
    Thread.__init__(self)

    self.socket = data_socket
    
    self.client_socket: socket.socket = None

    self.callback: Callable[[socket.socket], Reply] = None
    self.is_running = True

    self.reply: Reply = None

  def __del__(self) -> None:
    self.socket.close()

  def close(self) -> None:
    self.is_running = False
  
  def set_callback(self, callback: Callable[[socket.socket], Reply]) -> None:
    self.callback = callback

  def run(self):
    while self.is_running:
      if not self.client_socket:
        self.client_socket, _ = self.socket.accept()
      
      if self.callback:
        self.reply = self.callback(self.client_socket)
        self.client_socket.close()

        self.callback = None

  @staticmethod
  def is_port_open(host, port):
    data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    result = data_socket.connect_ex((host, port))
    data_socket.close()

    return result

  @staticmethod
  def handle(command_socket: socket.socket, data_handler, callback: Callable[[], None]) -> None:
    start_time = time.perf_counter()

    while True:
      reply = data_handler.reply
      if reply:
        command_socket.sendall(reply.get().encode("utf-8"))
        break

      if time.perf_counter() - start_time > 3.0:
        break
    
    callback()


class FileRenaming:
  def __init__(self, source) -> None:
    self.source = source

  def execute(self, target) -> None:
    os.rename(self.source, target)


class DataConnection:
  def __init__(self) -> None:
    self.type = "ascii"
    self.handler: DataHandler = None
    self.executor: Thread = None

  def get_read_type(self) -> str:
    if self.type == "utf-8":
      return "rb"
    elif self.type == "ascii":
      return "r"

  def get_write_type(self) -> str:
    if self.type == "utf-8":
      return "wb"
    elif self.type == "ascii":
      return "w"

  def get_mode_type(self) -> str:
    if self.type == "utf-8":
      return "Binary"
    elif self.type == "ascii":
      return "ASCII"

  def set_handler(self, handler: DataHandler) -> None:
    self.handler = handler
    self.handler.start()

  def set_type(self, type) -> None:
    if type == "I":
      self.type = "utf-8"

    if type == "A":
      self.type = "ascii"

  def close(self) -> None:
    if self.handler:
      self.handler.close()
      self.handler.join()
      self.handler = None

    self.executor = None

  def check_connection(self) -> Optional[Reply]:
    if not self.handler:
      return Reply(425, "Use PASV first.")

    return None
  
  def run(self, command_socket: socket.socket) -> None:
    if self.handler and self.handler.callback and not self.executor:
      self.executor = Thread(target=DataHandler.handle, args=(command_socket, self.handler, self.close))
      self.executor.start()


class CommandHandler(Thread):
  def __init__(self, host: str, socket: socket.socket, root: str, user: str, passwd: str) -> None:
    Thread.__init__(self)

    self.host = host
    self.root = root
    self.user = user
    self.passwd = passwd
    self.workdir = "/"

    self.socket = socket

    self.reply = Reply(220, "(myFTP 0.0.0)")
    self.is_running = True

    self.data_connection: DataConnection = DataConnection()

    self.file_renaming: FileRenaming = None

  def __del__(self) -> None:
    self.socket.close()
  
  def check_auth(self) -> Optional[Reply]:
    if len(self.user) or len(self.passwd):
      return Reply(530, "Please login with USER and PASS.")

    return None
  
  def validate_user(self, user) -> Reply:
    if self.user != user:
      return Reply(530, "Permission denied.")
    
    self.user = ""
    return Reply(331, "Please specify the password.")
  
  def validate_password(self, passwd) -> Reply:
    if len(self.user):
      return Reply(503, "Login with USER first.")

    if self.passwd != passwd:
      return Reply(530, "Login incorrect.")
    
    self.passwd = ""
    return Reply(230, "Login successful.")

  def handle_directory(self, path: str) -> str:
    directory = self.workdir
    if len(path):
      if path[0] != "/":
        directory += "/" + path
      
      else:
        directory = path
    
    return Path.merge(self.root, directory)

  def cwd(self, directory: str) -> Reply:
    if directory:
      if os.path.isdir(self.handle_directory(directory)):
        if directory[0] != "/":
          self.workdir += directory
        
        else:
          self.workdir = directory

        return Reply(250, "Directory successfully changed.")

    return Reply(550, "Failed to change directory.")

  def type(self, type: str) -> Reply:
    if type in ["A", "I"]:
      self.data_connection.set_type(type)
      return Reply(200, f"Switching to {self.data_connection.get_mode_type()} mode.")

    else:
      return Reply(500, "Unrecognized TYPE command.")

  def pasv(self) -> Reply:
    port = None
    start_time = time.perf_counter()

    while True:
      port = randint(59999, 65535)

      if DataHandler.is_port_open(self.host, port):
        break

      if time.perf_counter() - start_time > 3.0:
        break

    if port:
      data_socket = Socket(self.host, port)

      if data_socket.connect():
        self.data_connection.set_handler(DataHandler(data_socket.get()))

        address = self.host.replace('.', ',')
        port = [int(port / 256), (port % 256)]

        return Reply(227, f"Entering Passive Mode ({address},{port[0]},{port[1]}).")

    return Reply(421, "Failed to enter Passive Mode.")

  def ls(self, directory: str) -> Reply:
    directory = self.handle_directory(directory)

    def callback(client_socket: socket.socket) -> Reply:
      try:
        items = ""

        if os.path.exists(directory):
          for item in os.popen(f"ls -n {directory}").readlines():
            if len(item) and (item[0] == '-' or item[0] == 'd'):
              items += item.replace('\n', "")
              items += "\r\n"

        client_socket.sendall(items.encode(self.data_connection.type))
        return Reply(226, "Directory send OK.")

      except Exception as e:
        return Reply.handle_error(e)

    self.data_connection.handler.set_callback(callback)

    return Reply(150, "Here comes the directory listing.")

  def retr(self, filenames: List[str]) -> Reply:
    if len(filenames):
      callback = None

      filename = filenames[0]
      filepath = self.handle_directory(filename)
      filesize = 0

      if os.path.isfile(filepath):
        filesize = os.path.getsize(filepath)

        def callback(client_socket: socket.socket) -> Reply:
          try:
            content = ""
            with open(filepath, self.data_connection.get_read_type()) as file:
              content = file.read()

            if self.data_connection.type == "ascii":
              content = content.encode(self.data_connection.type)

            client_socket.sendall(content)
            return Reply(226, "Transfer complete.")

          except Exception as e:
            return Reply.handle_error(e)

      if callback:
        self.data_connection.handler.set_callback(callback)
        return Reply(150, f"Opening {self.data_connection.get_mode_type()} mode data connection for {filename} ({filesize} bytes).")

      else:
        self.data_connection.handler = None

    return Reply(550, "Failed to open file.")

  def stor(self, filenames: str) -> Reply:
    if len(filenames):
      filename = filenames[0]

      if len(filenames) == 2:
        filename = filenames[1]

      def callback(client_socket: socket.socket) -> Reply:
        try:
          filepath = self.handle_directory(filename)
          print(filepath)
          
          content = b""

          while True:
            buffer = client_socket.recv(1024)

            if buffer:
              content += buffer
            else:
              break

          with open(filepath, self.data_connection.get_write_type()) as file:
            if (self.data_connection.type == "ascii"):
              content = content.decode("utf-8")
            file.write(content)
          return Reply(226, "Transfer complete.")

        except Exception as e:
          return Reply.handle_error(e)

      self.data_connection.handler.set_callback(callback)

    return Reply(150, "Ok to send data.")

  def rnfr(self, source) -> Reply:
    if source:
      source = self.handle_directory(source)
      if os.path.exists(source):
        self.file_renaming = FileRenaming(source)

        return Reply(350, "Ready for RNTO.")

    return Reply(550, "RNFR command failed.")

  def rnto(self, target) -> Reply:
    if not self.file_renaming:
      return Reply(503, "RNFR required first.")

    if target:
      try:
        self.file_renaming.execute(self.handle_directory(target))
        return Reply(250, "Rename successful.")

      except Exception as e:
        return Reply.handle_error(e)

    return Reply(550, "Rename failed.")

  def mkd(self, directory) -> Reply:
    if directory:
      try:
        os.mkdir(self.handle_directory(directory))
        if self.workdir != "/":
          directory = "/" + directory
        return Reply(250, f"\"{self.workdir + directory}\" created.")

      except Exception as e:
        return Reply.handle_error(e)

    return Reply(550, "Create directory operation failed.")

  def pwd(self) -> Reply:
    return Reply(257, f"\"{self.workdir}\" is the current directory.")

  def help(self) -> Reply:
    self.socket.sendall(("214-The following commands are recognized.\r\n" +
      "CD  CWD  DELE HELP LIST LS   MKD  PASS PASV\r\n" +
      "PWD QUIT RETR RMD  RNFR RNTO STOR TYPE USER\r\n").encode("utf-8"))
    return Reply(214, "Help OK.")

  def dele(self, filename) -> Reply:
    if filename:
      filepath = self.handle_directory(filename)

      try:
        if os.path.isfile(filepath):
          os.remove(filepath)

          return Reply(250, "Delete operation successful.")
      
      except Exception as e:
        return Reply.handle_error(e)

    return Reply(550, "Delete operation failed.")
  
  def rmd(self, directory) -> Reply:
    if directory:
      directory = self.handle_directory(directory)

      try:
        if os.path.isdir(directory):
          os.rmdir(directory)

          return Reply(250, "Remove directory operation successful.")
      
      except Exception as e:
        return Reply.handle_error(e)

    return Reply(550, "Remove directory operation failed.")

  def run(self):
    while self.is_running:
      command = self.socket.recv(4096).decode("utf-8")

      print(self.socket.getpeername(), end=": ")
      print(command)

      if command:
        try:
          commands = command.split()
          command = commands[0]

          argument = [""]
          if len(commands) > 1:
            argument = commands[1:]

          reply = Reply()

          if command in ["CD", "CWD", "DELE", "HELP", "LIST", \
            "LS", "MKD", "PASS", "PASV", "PWD", "QUIT", "RETR", \
            "RMD", "RNFR", "RNTO", "STOR", "TYPE", "USER"]:

            if command == "USER":
              reply = self.validate_user(argument[0])

            elif command == "QUIT":
              reply = Reply(221, "Goodbye.")
              self.is_running = False

            elif command == "PASS":
              reply = self.validate_password(argument[0])

            elif not self.check_auth():
              if command == "CWD" or command == "CD":
                reply = self.cwd(argument[0])

              elif command == "TYPE":
                reply = self.type(argument[0])

              elif command == "PASV":
                reply = self.pasv()

              elif command == "RNFR":
                reply = self.rnfr(argument[0])

              elif command == "RNTO":
                reply = self.rnto(argument[0])

              elif command == "MKD":
                reply = self.mkd(argument[0])

              elif command == "PWD":
                reply = self.pwd()

              elif command == "HELP":
                reply = self.help()

              elif command == "DELE":
                reply = self.dele(argument[0])

              elif command == "RMD":
                reply = self.rmd(argument[0])

              elif command in ["LIST", "LS", "RETR", "STOR"]:
                if not self.data_connection.check_connection():
                  if command == "LIST" or command == "LS":
                    reply = self.ls(argument[0])

                  elif command == "RETR":
                    reply = self.retr(argument)

                  elif command == "STOR":
                    reply = self.stor(argument)

                else:
                  reply = self.data_connection.check_connection()

            else:
              reply = self.check_auth()

            if self.reply:
              reply = self.reply + reply
              self.reply = None

          self.data_connection.run(self.socket)

          self.socket.sendall(reply.get().encode("utf-8"))

        except Exception as e:
          self.socket.sendall(Reply.handle_error(e).get().encode("utf-8"))

      else:
        break

    self.data_connection.close()
