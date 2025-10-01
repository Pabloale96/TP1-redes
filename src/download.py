from lib.client import Client
import argparse
import time  

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
    parser.add_argument('-d', '--dst',
                        type=str,
                        required=True,
                        help="destination file path")
    parser.add_argument('-n', '--name',
                        type=str,
                        default="",
                        help="file name")
    parser.add_argument('-r', '--protocol',
                        type=str, default="",
                        help="Error recovery protocol")
    args = parser.parse_args()

    if args.quiet and args.verbose:
        parser.error("argumento -q/--quiet: no esta permito con el argumento -v/--verbose")

    client = Client(args.addr, args.port, args.dst, args.name, args.verbose, args.quiet, 1, args.protocol)
    start = time.time()
    client.download()
    end = time.time()
    client.close()
    print(f"Se termino de cargar en: {end-start:.4f} seconds")
