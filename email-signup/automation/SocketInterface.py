import queue
import threading
import traceback
import socket
import struct
import json
import dill
import six

#TODO - Implement a cleaner shutdown for server socket
# see: https://stackoverflow.com/questions/1148062/python-socket-accept-blocks-prevents-app-from-quitting

class serversocket:
    """
    A server socket to recieve and process string messages
    from client sockets to a central queue
    """
    def __init__(self, verbose=False):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(('localhost', 0))
        self.sock.listen(10)  # queue a max of n connect requests
        self.verbose = verbose
        self.queue = queue.Queue()
        if self.verbose:
            print("Server bound to: " + str(self.sock.getsockname()))

    def start_accepting(self):
        """ Start the listener thread """
        thread = threading.Thread(target=self._accept, args=())
        thread.daemon = True  # stops from blocking shutdown
        thread.start()

    def _accept(self):
        """ Listen for connections and pass handling to a new thread """
        while True:
            try:
                (client, address) = self.sock.accept()
            except:
                # TODO: handle [Errno 9] Bad file descriptor
                # currently the program just hangs here...
                raise
            thread = threading.Thread(target=self._handle_conn, args=(client, address))
            thread.daemon = True
            thread.start()

    def _handle_conn(self, client, address):
        """
        Recieve messages and pass to queue. Messages are prefixed with
        a 4-byte integer to specify the message length and 1-byte character
        to indicate the type of serialization applied to the message.

        Supported serialization formats:
            'n' : no serialization
            'd' : dill pickle
            'j' : json
        """
        if self.verbose:
            print("Thread: " + str(threading.current_thread()) + " connected to: " + str(address))
        try:
            while True:
                msg = self.receive_msg(client, 5)
                # print(type(msg))
                msglen, serialization = struct.unpack('>Lc', msg)
                if self.verbose:
                    print("Msglen: " + str(msglen) + " is_serialized: " + str(serialization != 'n'))
                msg = self.receive_msg(client, msglen)
                if serialization != b'n':
                    try:
                        if serialization == b'd': # dill serialization
                            msg = dill.loads(msg)
                        elif serialization == b'j': # json serialization
                            msg = json.loads(msg.decode('latin-1'))
                        else:
                            print("Unrecognized serialization type: %s" % serialization)
                            continue
                    except (UnicodeDecodeError, ValueError) as e:
                        print("Error de-serializing message: %s \n %s" % (
                                msg, traceback.format_exc(e)))
                        continue
                self.queue.put(msg)
        except RuntimeError:
            if self.verbose:
                print("Client socket: " + str(address) + " closed")

    def receive_msg(self, client, msglen):
        msg = b''
        #print(type(msg), msg)
        while len(msg) < msglen:
            chunk = client.recv(msglen-len(msg))
            # chunk = chunk.decode('latin-1')
            # print(type(chunk), chunk)
            if chunk == b'':
                raise RuntimeError("socket connection broken")
            # print(msg, chunk)
            msg = msg + chunk
            #print(type(msg), msg, type(chunk), chunk)
        return msg

    def close(self):
        self.sock.close()

class clientsocket:
    """A client socket for sending messages"""
    def __init__(self, serialization = 'json', verbose=False):
        """ `serialization` specifies the type of serialization to use for
        non-str messages. Supported formats:
            * 'json' uses the json module. Cross-language support. (default)
            * 'dill' uses the dill pickle module. Python only.
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if serialization != 'json' and serialization != 'dill':
            raise ValueError("Unsupported serialization type: %s" % serialization)
        self.serialization = serialization
        self.verbose = verbose

    def connect(self, host, port):
        if self.verbose: print("Connecting to: %s:%i" % (host, port))
        self.sock.connect((host, port))

    def send(self, msg):
        """
        Sends an arbitrary python object to the connected socket. Serializes
        using dill if not str, and prepends msg len (4-bytes) and
        serialization type (1-byte).
        """
        #if input not string, serialize to string
        if type(msg) is not str:
            if self.serialization == 'dill':
                msg = dill.dumps(msg)
                serialization = b'd'
            elif self.serialization == 'json':
                msg = json.dumps(msg)
                serialization = b'j'
            else:
                raise ValueError("Unsupported serialization type set: %s" % serialization)
        else:
            serialization = b'n'

        if self.verbose: print("Sending message with serialization %s" % serialization)

        #prepend with message length
        # serialization = bytes(serialization, "utf-8")
        print(msg.decode("latin-1"), serialization.decode("latin-1"))
        print(type(msg), type(serialization), type(struct.pack('>Lc', len(msg), serialization)))
        msg = struct.pack('>Lc', len(msg), serialization) + msg
        totalsent = 0
        while totalsent < len(msg):
            sent = self.sock.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent = totalsent + sent

    def close(self):
        self.sock.close()

if __name__ == '__main__':
    import sys

    #Just for testing
    if sys.argv[1] == 's':
        sock = serversocket(verbose=True)
        sock.start_accepting()
        input("Press enter to exit...")
        sock.close()
    elif sys.argv[1] == 'c':
        host = input("Enter the host name:\n")
        port = input("Enter the port:\n")
        serialization = input("Enter the serialization type (default: 'json'):\n")
        if serialization == '':
            serialization = 'json'
        sock = clientsocket(serialization=serialization)
        sock.connect(host, int(port))
        msg = b''

        # some predefined messages
        tuple_msg = ('hello','world')
        list_msg = ['hello','world']
        dict_msg = {'hello':'world'}
        def function_msg(x): return x

        # read user input
        while msg != b"quit":
            msg = input("Enter a message to send:\n")
            if msg == b'tuple':
                sock.send(six.b(tuple_msg))
            elif msg == b'list':
                sock.send(six.b(list_msg))
            elif msg == b'dict':
                sock.send(six.b(dict_msg))
            elif msg == b'function':
                sock.send(six.b(function_msg))
            else:
                sock.send(six.b(msg))
        sock.close()
