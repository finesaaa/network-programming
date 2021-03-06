import os
import re
from tqdm import tqdm


def validate_header(socket) -> bool:
  header = b''
  header_comma_counter = 0
  header_end_flag = 3

  file_name = ''
  file_size = 0

  while True:
    response = socket.recv(1)
    if response:
      header += response

    else:
      header = b''
      break
    
    if header_comma_counter >= 2:
      header_end_flag -= 1
    
    if response == b',':
      header_comma_counter += 1
    
    if header_end_flag <= 0:
      break
  
  if len(header) != 0:
    contents = re.findall(r': [\w\.-]+,', header.decode('utf-8'))
    file_name = contents[0][2:-1]
    file_size = int(contents[1][2:-1])

  return len(header), file_name, file_size


def handle_receive_file(socket) -> None:
  header_size, file_name, file_size = validate_header(socket)

  if header_size != 0:
    if file_size == 0:
      print("file exists but there is someting goes wrong, please try again!")
    elif file_size == -1:
      print("file doesn't exist")
    else:
      bar = tqdm(range(file_size), f"downloading {file_name}", unit="B", unit_scale=True, unit_divisor=round(1024))
      data = b''

      while len(data) < file_size:
        reponse = socket.recv(file_size - len(data))

        if reponse:
          data += reponse
        
        bar.update(len(data))

      with open(os.path.dirname(__file__) + "/dataset/" + file_name, 'wb') as file:
        file.write(data)
