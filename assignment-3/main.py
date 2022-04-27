import argparse
import sys
from typing import Tuple
from ftp import FTPClient


def get_ftp(args: argparse.Namespace) -> Tuple[FTPClient, bool]:
  ftp = FTPClient(args.host, args.port)
  is_logged_in = ftp.login(args.user, args.passwd)

  return ftp, is_logged_in


def problem_1(args: argparse.Namespace):
  ftp, _ = get_ftp(args)

  for response in ftp.responses:
    if '220' in response:
      message = response.replace('220', '').strip(' ()')
      print(message)


def problem_2(args: argparse.Namespace):
  ftp, _ = get_ftp(args)

  ftp.send(['SYST\r\n'])
  print("success")


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Connect HTTPClient on defined host and port')
  parser.add_argument('--host', help='specify the host that will be connected to', type=str, default='localhost')
  parser.add_argument('--port', help='specify the port which is used', type=int, default=21)
  parser.add_argument('--user', help='specify the username that will be used to login', type=str, default='netpro')
  parser.add_argument('--passwd', help='enter the password corespond with the user', type=str, default='123')

  args = parser.parse_args()
  if ('--user' in vars(args) and '--passwd' not in vars(args)):
    parser.error('the --user argument requires the --passwd')

  try:
    while True:
      print('>> ', end='')
      command = input()

      if "1" in command:
        problem_1(args)

      if "2" in command:
        problem_2(args)

  except KeyboardInterrupt:
    sys.exit(0)