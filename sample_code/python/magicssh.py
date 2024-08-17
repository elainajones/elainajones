import time

import sshtunnel
import paramiko
from fabric import Connection


class MagicSSH:
    """SSH client using Fabric

    Convienient wrapper for SSH that extends functions from Fabric's
    low level Paramiko client object. These methods facilitate usage
    of interactive SSH channels.

    Fabric executes individual run commands in new shells, garbage
    collecting them between invocation. Alternatively, the send() and
    recv() functions use interactive channels that allow for sequential
    command exectution within the same SSH session.

    Fabric is the recommended tool for common client use-cases such as
    running remote shell commands or transferring files. Please refer
    to Fabric methods for more infomation.

    https://www.fabfile.org/

    Attributes:
        client: Fabric ssh connection object.
        channel: Paramiko ssh socket for sending/receiving ssh commands.
        tunnel: SSH tunnel for forwarding local connections..
    """
    def __init__(
        self,
        host: str,
        user: str,
        port: int,
        password: str = None,
        pkey: str = None
    ) -> None:
        """Initializes the SSH client connection.

        Args:
            host: Host ip address.
            user: Host user name.
            port: SSH port number.
            password: SSH password for client authentication,
                if applicable.
            pkey: Path to private key for host authentication,
                if applicable.
        """
        # Disable annoying debug output.
        paramiko.util.logging.disable(level='DEBUG')

        self.__host = host
        self.__user = user
        self.__port = port
        self.__password = password
        self.__pkey = pkey

        self.client = None
        self.channel = None
        self.tunnel = None

        if password:
            self.client = Connection(
                host=host,
                user=user,
                port=port,
                connect_kwargs={
                    "password": password,
                },
            )
        elif pkey:
            self.client = Connection(
                host=host,
                user=user,
                port=port,
                connect_kwargs={
                    "key_filename": pkey,
                    "look_for_keys": False,
                },
            )

        self.__connect()

    def __connect(self) -> None:
        """Establishes client SSH connection.

        """
        try:
            self.client.open()
        except paramiko.ssh_exception.SSHException:
            pass

    def send(self, s: str) -> None:
        """Sends data to the SSH channel.

        Newline (enter) characters are not appended by default and
        must be handled by applications using this method.

        Args:
            s: Data to send.
        """
        # Automatically handle channel creation.
        if not self.channel:
            self.channel = self.client.client.invoke_shell()
            self.channel.set_combine_stderr(True)
            self.channel.setblocking(0)
        elif self.channel.closed:
            self.__connect()
            self.channel = self.client.client.invoke_shell()
            self.channel.set_combine_stderr(True)
            self.channel.setblocking(0)

        # TODO: Verify all data was sent by checking nbytes returned by send()
        self.channel.send(s)

    def recv(self, nbytes: int = 1024) -> bytes:
        """Recieve data from the SSH channel.

        Args:
            nbytes: Number of bytes to receive from the channel.
            timeout: Number of seconds to block for channel to receive
                data. If None, channel is nonblocking.
        """
        res = None
        if not self.channel:
            self.channel = self.client.client.invoke_shell()
            self.channel.set_combine_stderr(True)
            self.channel.setblocking(0)
        elif self.channel.closed:
            self.__connect()
        elif self.channel.recv_ready():
            res = self.channel.recv(nbytes)

        return res

    def recv_all(self, timeout: float, interval: float = 0.25) -> bytes:
        """Recieves data from the SSH channel until timeout.

        Intended only for situations where run() is not applicable,
        such as interactive sessions.

        If no more data is recvieved after consecutive attempts,
        assume all data has been recieved. This is often useful
        when reading command output without knowing the exact length,
        including when output is intermittent.

        Args:
            timeout: Time in seconds to read. We return sooner when
                no data is left so this is mainly to prevent infinite
                waits.
            interval: Time to wait between recv() calls.

        Returns:
            Data received as bytes.
        """
        time_start = time.time()

        res_all = b''
        # Number of times to recheck the response after recieving
        # nothing, used to indicate that we've recieved
        # everything.
        retries = 3
        while time.time() - time_start < timeout:
            res = self.recv() or b''
            res_all += res
            time.sleep(interval)

            if retries <= 0:
                break
            elif not res:
                retries -= 1
            else:
                retries = 3

        return res_all

    def close(self) -> None:
        """Terminate the network connection to the remote end, if open.

        If any SFTP are open, they will also be closed.
        """
        self.client.close()
        self.tunnel and self.tunnel.close()
        self.tunnel = None

    def put(self, local: str, remote: str = None) -> None:
        """Put a local file (or file-like object) to the remote filesystem.

        Args:
            local: File path or file-like object.
            remote: Desination path. This will use the OS user's home if None.
        """
        self.client.put(local=local, remote=remote)

    def get(self, remote: str, local: str = None) -> None:
        """Get a remote file to the local filesystem or file-like object.

        Args:
            remote: Remote path or file to copy from path.
            local: Local file path. This will use the OS user's current
                working directory if None.
        """
        self.client.get(remote=remote, local=local)

    def run(self, cmd: str) -> tuple:
        """Execute a shell command on the remote end of this connection.

        Fabric uses a setting in the SSH layer which merges both
        stderr and stdout streams at a low level to cause output to
        appear more naturally at the cost of an empty .stderr attribute.

        https://docs.fabfile.org/en/1.11/usage/interactivity.html

        Args:
            cmd: Command to execute.

        Returns:
            Tuple of output and return code.
        """
        result = self.client.run(cmd, hide=True)

        return result.stdout, result.return_code

    def forward_local(
        self,
        local_port: int,
        remote_port: int,
        remote_host: str,
        local_host: str = 'localhost',
    ) -> bool:
        """Opens a tunnel connecting local_port to the remote_host.

        Handles tunnel creation and start. To check tunnel connection
        status, the following attribures may be evaluated:

        - self.tunnel.is_alive
        - self.tunnel.is_active

        Due to a lack of success with Fabric's forward_local() method,
        this method uses similar naming but wraps sshtunnel instead.

        Args:
            local_port: Local port to forward.
            remote_port: Remote port to bind to.
            remote_host: Remote server ip address.
            local_host: Local hostname to listen.

        Returns:
            Boolean indicating whether a tunnel could be started.

        """
        try:
            # Close any existing tunnels.
            self.tunnel and self.tunnel.close()
            self.tunnel = sshtunnel.open_tunnel(
                (self.__host, self.__port),
                ssh_username=self.__user,
                ssh_password=self.__password,
                remote_bind_address=(remote_host, remote_port),
                local_bind_address=(local_host, local_port)
            )
            self.tunnel.logger.disabled = True
            self.tunnel.start()
        except sshtunnel.HandlerSSHTunnelForwarderError:
            pass

    def tunnel_is_up(self) -> bool:
        """Check if forwarded SSH connection is up.

        Returns:
            Boolean indicating whether the tunneled SSH server
                is up.

        """
        if not self.tunnel:
            status = False
        else:
            self.tunnel.check_tunnels()
            status = self.tunnel.tunnel_is_up.get(
                self.tunnel.local_bind_address, False
            )

        return status
