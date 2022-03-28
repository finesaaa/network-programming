import socket
import select
from typing import Callable, List


class Response:
  def __init__(self):
    self.status_code = 200
    self.status = 'OK'

    self.type = ''
    self.data_length = 0

    self.body = ''

  def create(self) -> bytes:
    return (
      b'HTTP/1.1 {self.status_code} {self.status}\r\n'
      b'Content-Type: {self.type}\r\n'
      b'Content-Length: {self.data_length}\r\n'
      b'\r\n'
      + self.body.encode('utf-8')
    )

  @staticmethod
  def get_404_response() -> Response:
    response = Response()
    
    content = ''
    with open('./404.html', 'r') as file:
      content = file.read()

    response.status_code = 404
    response.status = 'Not found'
    response.type = 'text/html; charset=UTF-8'
    response.data_length = len(content)
    response.body = content

    return response


class Route:
  def __init__(self, routes: List[str], response_callback: Callable[[], Response]):
    self.routes = routes
    self.response_callback = response_callback

  def is_match(self, response) -> bool:
    data = response.decode("utf-8")
    request_header = data.split("\r\n")
    requested_route = request_header[0].split()[1]

    if len(self.routes) > 0:
      for route in self.routes:
        if requested_route == route:
          return True
    
    return False


class HttpServer:
  def __init__(self, host, port):
    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    self.host = host
    self.port = port

    self.input_sockets = []

    self.routes: List[Route] = []

  def __del__(self):
    self.socket.close()

  def add_route(self, route: Route):
    self.routes.append(route)

  def connect(self) -> bool:
    try:
      self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
      try:
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
      except AttributeError:
        pass

      self.socket.bind((self.host, self.port))
      self.socket.listen(100)

      self.input_sockets.append(self.socket)

      return True

    except Exception:
      return False

  def run(self):
    read_ready_sockets, _, _ = select.select(self.input_sockets, [], [])

    for ready_socket in read_ready_sockets:
      if ready_socket == self.socket:
        client_socket, _ = self.socket.accept()
        self.input_sockets.append(client_socket)

      else:
        request = ready_socket.recv(4096)
        is_match = False

        response = b''
        for route in self.routes:
          if route.is_match(request):
            response = route.response_callback().create()
            is_match = True

            break

        if not is_match:
          response = Response.get_404_response().create()

        self.socket.sendall(response)