import argparse
from lib.server import server

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='start-server.py',
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
                        help="service IP address")
    parser.add_argument('-p', '--port',
                        type=int, 
                        default=65432,
                        help="service port")
    parser.add_argument('-s', '--dirpath',
                        type=str,
                        default="",
                        help="storage dir path")
    args = parser.parse_args()

    if args.verbose:
        print(args.addr)
        print(args.port)
        print(args.dirpath)

    server = server(args.addr, args.port)
    server.upload()
