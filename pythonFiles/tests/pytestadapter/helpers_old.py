# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import asyncio
import io
import json
import os
import pathlib
import socket
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple

# import win32pipe
# import win32file
# import pywintypes

script_dir = pathlib.Path(__file__).parent.parent.parent
sys.path.append(os.fspath(script_dir))
sys.path.append(os.fspath(script_dir / "lib" / "python"))

TEST_DATA_PATH = pathlib.Path(__file__).parent / ".data"
from typing_extensions import TypedDict
from pythonFiles.testing_tools import socket_manager


# class NamedPipeReader:
# def __init__(self, handle):
#     self.handle = handle

# async def read(self, n):
#     loop = asyncio.get_running_loop()
#     data = await loop.run_in_executor(None, win32file.ReadFile, self.handle, n)
#     # data[1] contains the actual data read
#     return data[1]


# class NamedPipeWriter:
#     def __init__(self, handle):
#         self.handle = handle

#     async def write(self, data):
#         loop = asyncio.get_running_loop()
#         await loop.run_in_executor(None, win32file.WriteFile, self.handle, data)

#     async def close(self):
#         await asyncio.get_running_loop().run_in_executor(
#             None, win32file.CloseHandle, self.handle
#         )


# async def handle_client(reader, writer):
#     data = await reader.read(1024)
#     print(f"Received: {data.decode()}")
#     await writer.write(b"Hello from server")
#     await writer.close()


class PipeManager:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        return self.listen()

    def __exit__(self, *_):
        self.close()

    def listen(self):
        # find library that creates named pipes for windows

        if sys.platform == "win32":
            # create a pipe
            # create a reader, writer stream from the pipe
            # no return (just set _reader and _writer)

            pipe_name = r"\\.\pipe\mypipe"

            # pipe = win32pipe.CreateNamedPipe(
            #     pipe_name,
            #     win32pipe.PIPE_ACCESS_DUPLEX,
            #     win32pipe.PIPE_TYPE_MESSAGE
            #     | win32pipe.PIPE_READMODE_MESSAGE
            #     | win32pipe.PIPE_WAIT,
            #     1,
            #     65536,
            #     65536,
            #     0,
            #     None,
            # )

            # if pipe == -1:
            #     print("Failed to create named pipe, in test helper file. Exiting.")
            # else:
            #     print(f"Named pipe {pipe_name} created")

            # win32pipe.ConnectNamedPipe(pipe, None)
            # self._reader = NamedPipeReader(pipe)
            # self._writer = NamedPipeWriter(pipe)

        else:
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.listen(self.name)  # self.name = named pipe
            (
                _sock,
                _,
            ) = (
                server.accept()
            )  # occurs when client connects, returns a socket (_sock) which will be used for this specific
            # client and server connection
            self._socket = _sock
        return self

    def close(self):
        if sys.platform == "win32":
            self._writer.close()
            # close the streams and the pipe
        else:
            # add exception catch
            self._socket.close()

    def write(self, data: str):
        # must include the carriage-return defined (as \r\n) for unix systems
        request = f"""content-length: {len(data)}\r\ncontent-type: application/json\r\n\r\n{data}"""
        if sys.platform == "win32":
            # this should work
            self._writer.write(request)
            self._writer.flush()
        else:
            self._socket.send(request.encode("utf-8"))
            # does this also need a flush on the socket?

    def read(self, bufsize=1024):
        """Read data from the socket.

        Args:
            bufsize (int): Number of bytes to read from the socket.

        Returns:
            data (bytes): Data received from the socket.
        """
        if sys.platform == "win32":
            # this should work
            return self._reader.read(bufsize)
        else:
            data = b""
            while True:
                part = self._socket.recv(bufsize)
                data += part
                if len(part) < bufsize:
                    # No more data, or less than bufsize data received
                    break
            return data


def get_absolute_test_id(test_id: str, testPath: pathlib.Path) -> str:
    split_id = test_id.split("::")[1:]
    absolute_test_id = "::".join([str(testPath), *split_id])
    print("absolute path", absolute_test_id)
    return absolute_test_id


# def create_server(
#     host: str = "127.0.0.1",
#     port: int = 0,
#     backlog: int = socket.SOMAXCONN,
#     timeout: int = 1000,
# ) -> socket.socket:
#     """Return a local server socket listening on the given port."""
#     server: socket.socket = _new_sock()
#     if port:
#         # If binding to a specific port, make sure that the user doesn't have
#         # to wait until the OS times out waiting for socket in order to use
#         # that port again if the server or the adapter crash or are force-killed.
#         if sys.platform == "win32":
#             server.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
#         else:
#             try:
#                 server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#             except (AttributeError, OSError):
#                 pass  # Not available everywhere
#     server.bind((host, port))
#     if timeout:
#         server.settimeout(timeout)
#     server.listen(backlog)
#     return server


async def create_pipe(test_run_pipe: str) -> socket.socket:
    __pipe = socket_manager.PipeManager(test_run_pipe)
    return __pipe


# def _new_sock() -> socket.socket:
#     sock: socket.socket = socket.socket(
#         socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP
#     )
#     options = [
#         ("SOL_SOCKET", "SO_KEEPALIVE", 1),
#         ("IPPROTO_TCP", "TCP_KEEPIDLE", 1),
#         ("IPPROTO_TCP", "TCP_KEEPINTVL", 3),
#         ("IPPROTO_TCP", "TCP_KEEPCNT", 5),
#     ]

#     for level, name, value in options:
#         try:
#             sock.setsockopt(getattr(socket, level), getattr(socket, name), value)
#         except (AttributeError, OSError):
#             pass  # May not be available everywhere.

#     return sock


CONTENT_LENGTH: str = "Content-Length:"
Env_Dict = TypedDict(
    "Env_Dict", {"TEST_UUID": str, "TEST_PORT": str, "PYTHONPATH": str}
)


def process_rpc_message(data: str) -> Tuple[Dict[str, Any], str]:
    """Process the JSON data which comes from the server which runs the pytest discovery."""
    str_stream: io.StringIO = io.StringIO(data)

    length: int = 0

    while True:
        line: str = str_stream.readline()
        if CONTENT_LENGTH.lower() in line.lower():
            length = int(line[len(CONTENT_LENGTH) :])
            break

        if not line or line.isspace():
            raise ValueError("Header does not contain Content-Length")

    while True:
        line: str = str_stream.readline()
        if not line or line.isspace():
            break

    raw_json: str = str_stream.read(length)
    return json.loads(raw_json), str_stream.read()


def process_rpc_json(data: str) -> List[Dict[str, Any]]:
    """Process the JSON data which comes from the server which runs the pytest discovery."""
    json_messages = []
    remaining = data
    while remaining:
        json_data, remaining = process_rpc_message(remaining)
        json_messages.append(json_data)

    return json_messages


def runner(args: List[str]) -> Optional[List[Dict[str, Any]]]:
    """Run the pytest discovery and return the JSON data from the server."""
    return runner_with_cwd(args, TEST_DATA_PATH)


def runner_with_cwd(
    args: List[str], path: pathlib.Path
) -> Optional[List[Dict[str, Any]]]:
    """Run the pytest discovery and return the JSON data from the server."""
    process_args: List[str] = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "vscode_pytest",
        "-s",
    ] + args

    # create a pipe with the pipe manager
    # when I create it will listen

    test_run_pipe = "fake-pipe"
    reader: socket.socket = create_pipe(test_run_pipe)
    # listener.listen()

    env = os.environ.copy()
    env.update(
        {
            "TEST_RUN_PIPE": test_run_pipe,
            "PYTHONPATH": os.fspath(pathlib.Path(__file__).parent.parent.parent),
        }
    )
    completed = threading.Event()

    result = []
    t1: threading.Thread = threading.Thread(
        target=_listen_on_pipe, args=(reader, result, completed)
    )
    t1.start()

    t2 = threading.Thread(
        target=_run_test_code,
        args=(process_args, env, path, completed),
    )
    t2.start()

    t1.join()
    t2.join()

    return process_rpc_json(result[0]) if result else None


# def _listen_on_socket(
#     listener: socket.socket, result: List[str], completed: threading.Event
# ):
#     """Listen on the socket for the JSON data from the server.
#     Created as a separate function for clarity in threading.
#     """
#     # listen in pipe manager, pass in pipeManager
#     # same ish, just use "read" instead of the specific sock.recv
#     sock, (other_host, other_port) = listener.accept()
#     listener.settimeout(1)
#     all_data: list = []
#     while True:
#         data: bytes = sock.recv(1024 * 1024)
#         if not data:
#             if completed.is_set():
#                 break
#             else:
#                 try:
#                     sock, (other_host, other_port) = listener.accept()
#                 except socket.timeout:
#                     result.append("".join(all_data))
#                     return
#         all_data.append(data.decode("utf-8"))
#     result.append("".join(all_data))


def _listen_on_pipe(
    listener: socket.socket, result: List[str], completed: threading.Event
):
    """Listen on the pipe for the JSON data from the server."""
    with listener as reader:
        # Read data from the pipe
        data = reader.read()
        print(data)


def _run_test_code(
    proc_args: List[str], proc_env, proc_cwd: str, completed: threading.Event
):
    result = subprocess.run(proc_args, env=proc_env, cwd=proc_cwd)
    completed.set()
    return result


def find_test_line_number(test_name: str, test_file_path) -> str:
    """Function which finds the correct line number for a test by looking for the "test_marker--[test_name]" string.

    The test_name is split on the "[" character to remove the parameterization information.

    Args:
    test_name: The name of the test to find the line number for, will be unique per file.
    test_file_path: The path to the test file where the test is located.
    """
    test_file_unique_id: str = "test_marker--" + test_name.split("[")[0]
    with open(test_file_path) as f:
        for i, line in enumerate(f):
            if test_file_unique_id in line:
                return str(i + 1)
    error_str: str = f"Test {test_name!r} not found on any line in {test_file_path}"
    raise ValueError(error_str)
