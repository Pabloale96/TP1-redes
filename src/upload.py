import argparse
from lib.client import client

string_to_number_map = {
    "SW": 1,
    "SR": 2
}

list_of_choices = ["SW", "SR"]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='upload.py',
                                     description="File Transfer",
                                     epilog='TP N#1: File Transfer ')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-v', '--verbose',
                       action='store_true',
                       help="increase output verbosity")
    group.add_argument('-q', '--quiet',
                       action='store_true',
                       help="decrease output verbosity")
    parser.add_argument('-H', '--addr',
                        type=str,
                        default="127.0.0.1",
                        help="server IP address")
    parser.add_argument('-p', '--port',
                        type=int, default=65432,
                        help="server port")
    parser.add_argument('-s', '--filepath',
                        type=str, default="",
                        help="src source file path")
    parser.add_argument('-n', '--filename',
                        type=str,
                        default="archivo.bin",
                        help="file name")
    parser.add_argument('-r', '--protocol',
                        type=str, default="SW",
                        choices=list_of_choices,
                        help="Stop & Wait or Selective Repeat[SW or SR]")
    args = parser.parse_args()

    if args.verbose:
        print(args.addr)
        print(args.port)
        print(args.filepath)
        print(args.filename)
        print(args.protocol)

client = client(args.addr, args.port)
client.upload(args.filepath,
              args.filename,
              string_to_number_map.get(args.protocol))
