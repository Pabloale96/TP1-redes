import argparse
import time

from lib.client import Client

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="upload.py", description="File Transfer", epilog="TP N#1: File Transfer "
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-v", "--verbose", action="store_true", help="increase output verbosity"
    )
    group.add_argument(
        "-q", "--quiet", action="store_true", help="decrease output verbosity"
    )
    parser.add_argument(
        "-H", "--addr", type=str, default="127.0.0.1", help="server IP address"
    )
    parser.add_argument("-p", "--port", type=int, default=65432, help="server port")
    parser.add_argument(
        "-s", "--filepath", type=str, required=True, help="src source file path"
    )
    parser.add_argument("-n", "--filename", type=str, default="", help="file name")
    parser.add_argument(
        "-r",
        "--protocol",
        type=str,
        default="",
        help="Stop & Wait or Selective Repeat[SW or SR]",
    )
    args = parser.parse_args()

    if args.quiet and args.verbose:
        parser.error(
            "argument -q/--quiet: it is not permitted with the argument -v/--verbose"
        )

    client = Client(
        args.addr,
        args.port,
        args.filepath,
        args.filename,
        args.verbose,
        args.quiet,
        0,
        args.protocol,
    )

    try:
        start = time.time()
        stats = client.upload()
        end = time.time()
        print(f"It took {end-start:.4f} seconds to upload the file")
    except Exception as e:
        client.close()
        raise Exception("Error: {e}")
