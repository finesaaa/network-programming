import socket
from typing import List


class FTP:
  def __init__(self, host, port = 21):
    self.conn_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.data_socket: socket.socket = None

    FTP.handle_reuse(self.conn_socket)
    self.conn_socket.connect((host, port))

    self.responses: List[str] = []
  
  def __del__(self):
    self.conn_socket.close()

    if self.data_socket is not None:
      self.data_socket.close()
  
  @staticmethod
  def handle_reuse(sock: socket.socket):
    try:
      sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
      try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
      except AttributeError:
        pass

    except Exception:
      pass
  
  def send(self, commands: List[str]):
    for command in commands:
      self.conn_socket.send(command.encode('utf-8'))
      response = self.conn_socket.recv(1024)
      response = response.strip().decode('utf-8').split("\r\n")
      self.responses.extend(response)

  def login(self, user, passwd) -> bool:
    commands = [f'USER {user}\r\n', f'PASS {passwd}\r\n']
    self.send(commands)

    for response in self.responses:
      if '230' in response:
        return True

    return False
