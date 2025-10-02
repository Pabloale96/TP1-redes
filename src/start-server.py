import argparse

from lib.logger import logger
from lib.server import Server

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="start-server.py",
        description="File Transfer",
        epilog="TP N#1: File Transfer ",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-v", "--verbose", action="store_true", help="increase output verbosity"
    )
    group.add_argument(
        "-q", "--quiet", action="store_true", help="decrease output verbosity"
    )
    parser.add_argument(
        "-H", "--addr", type=str, default="127.0.0.1", help="service IP address"
    )
    parser.add_argument("-p", "--port", type=int, default=65432, help="service port")
    parser.add_argument(
        "-s", "--dirpath", type=str, default="", help="storage dir path"
    )
    args = parser.parse_args()

    if args.quiet and args.verbose:
        parser.error(
            "argument -q/--quiet: it is not permitted with the argument -v/--verbose"
        )

    logger.info("Initializing server...")
    server = Server(args.addr, args.port, storage_dir=args.dirpath)

    try:
        logger.info("Starting listening thread")
        server.start()
    except KeyboardInterrupt:
        logger.info("\nClosing server")

