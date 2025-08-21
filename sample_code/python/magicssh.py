import os
import posixpath
import stat
import time

from fabric import Connection, Config
from invoke.exceptions import UnexpectedExit
import paramiko
import sshtunnel


class MagicSSH:
    """SSH client using Fabric

    Convenient wrapper for SSH that extends functions from Fabric's
    low level Paramiko client object. These methods facilitate usage
    of interactive SSH channels.

    Fabric executes individual run commands in new shells, garbage
    collecting them between invocation. Alternatively, the send() and
    recv() functions use interactive channels that allow for sequential
    command execution within the same SSH session.

    Fabric is the recommended tool for common client use-cases such as
    running remote shell commands or transferring files. Please refer
    to Fabric methods for more information.

    https://www.fabfile.org/

    Attributes:
        client: Fabric ssh connection object.
        channel: Paramiko ssh socket for sending/receiving ssh commands.
        tunnels: SSH tunnel for forwarding local connections.
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
            host: Host IP address.
            user: Host user name.
            port: SSH port number.
            password: SSH password for client authentication,
                if applicable.
            pkey: Path to private key for host authentication,
                if applicable.
        """
        # Disable annoying debug output.
        paramiko.util.logging.disable(level='DEBUG')

        self.__config = Config()

        self.__host = host
        self.__user = user
        self.__port = port
        self.__password = password
        self.__pkey = pkey

        self.client = None
        self.channel = None
        self.tunnels = []

        if pkey:
            self.client = Connection(
                host=host,
                user=user,
                port=port,
                connect_kwargs={
                    "key_filename": pkey,
                    "look_for_keys": False,
                },
                config=self.__config,
            )
        elif password:
            self.__config = Config(
                overrides={'sudo': {'password': self.__password}}
            )
            self.client = Connection(
                host=host,
                user=user,
                port=port,
                connect_kwargs={
                    "password": password,
                },
                config=self.__config,
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
        """Receive data from the SSH channel.

        Args:
            nbytes: Number of bytes to receive from the channel.
            timeout: Number of seconds to block for channel to receive
                data. If None, channel is non-blocking.

        Returns:
            Response bytes.
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

    def recv_all(self, timeout: float = 15, interval: float = 0.25) -> bytes:
        """Receives data from the SSH channel until timeout.

        Intended only for situations where run() is not applicable,
        such as interactive sessions.

        If no more data is received after consecutive attempts,
        assume all data has been received. This is often useful
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
        self.tunnels and [i.close() for i in self.tunnels]
        self.tunnels = []

    def put(self, local: str, remote: str = None) -> None:
        """Put a local file (or file-like object) to the remote file system.

        Args:
            local: File path or file-like object.
            remote: Destination path. This will use the OS user's home if None.
        """
        sftp = self.client.sftp()
        # Convert remote path to posix for non-standard platforms.
        # Related bug: https://github.com/fabric/fabric/issues/2335
        remote = remote and sftp.normalize(remote)

        self.client.put(local=local, remote=remote)

    def get(self, remote: str, local: str = None) -> None:
        """Get a remote file to the local filesystem or file-like object.

        Args:
            remote: Remote path or file to copy from path.
            local: Local file path. This will use the OS user's current
                working directory if None.
        """
        sftp = self.client.sftp()
        # Convert remote path to posix for non-standard platforms.
        # Related bug: https://github.com/fabric/fabric/issues/2335
        remote = remote and sftp.normalize(remote)

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
        try:
            result = self.client.run(cmd, hide=True)
            result = (result.stdout, result.return_code)
        except UnexpectedExit as e:
            # Simple hack to preserve the expected behavior when an
            # UnexpectedExit occurs. This can occur when the command
            # fails on the remote host. For simple remote execution use
            # cases, these errors should be combined in `.stdout` and
            # the error reflected by the return code. Unfortunately,
            # this behavior isn't well supported and the result object
            # returns separate stderr and stdout attributes for this.
            #
            # With `pty=true`, the combined output is preserved but
            # `.return_code` may incorrectly reflect a 0 status and
            # `.ok` incorrectly reports True. With `warn=True` this
            # corrects `.return_code` and `.ok` but still splits the
            # stdout and stderr. Although more ideal, this is harder
            # to handle predictably than a catch for this specific
            # exception.
            result = e.result
            # Combine stderr and stdout.
            output = result.stdout + result.stderr
            # Make sure return code is non-zero so we can depend on it for
            # determining errors. In theory, this can still be more verbose
            # than a simple `.ok` which is why we don't use that instead.
            return_code = result.return_code != 0 and result.return_code or 1
            result = (output, return_code)

        return result

    def sudo(self, cmd: str) -> tuple:
        """Execute a shell command, via `sudo`, on the remote end.

        Simple wrapper for fabric.Connection.sudo()

        Args:
            cmd: Command to execute.

        Returns:
            Tuple of output and return code.
        """
        result = self.client.sudo(cmd, hide=True)

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
        status, the following attributes may be evaluated:

        - self.tunnel.is_alive
        - self.tunnel.is_active

        Due to a lack of success with Fabric's forward_local() method,
        this method uses similar naming but wraps sshtunnel instead.

        Related bug: https://github.com/fabric/fabric/issues/2102

        Args:
            local_port: Local port to forward.
            remote_port: Remote port to bind to.
            remote_host: Remote server IP address.
            local_host: Local hostname to listen.

        Returns:
            Boolean indicating whether a tunnel could be started.

        """
        try:
            self.tunnels.append(
                sshtunnel.open_tunnel(
                    (self.__host, self.__port),
                    ssh_username=self.__user,
                    ssh_password=self.__password,
                    remote_bind_address=(remote_host, remote_port),
                    local_bind_address=(local_host, local_port)
                )
            )
            self.tunnels[-1].logger.disabled = True
            self.tunnels[-1].start()

            return len(self.tunnels) - 1

        except sshtunnel.HandlerSSHTunnelForwarderError:
            return None

    def tunnel_is_up(self, index=-1) -> bool:
        """Check if forwarded SSH connection is up.

        Returns:
            Boolean indicating whether the tunneled SSH server
            is up.

        """
        if not self.tunnels:
            status = False
        else:
            self.tunnels[index].check_tunnels()
            status = self.tunnels[index].tunnel_is_up.get(
                self.tunnels[index].local_bind_address, False
            )

        return status

    def sftp_walk(self, path: str) -> tuple:
        """Walks through directories and files on an SFTP server.

        This method behaves similarly to os.walk(), but for SFTP.
        It yields a tuple containing the directory path, a list
        of subdirectories, and a list of files.

        Args:
            path (str): The remote directory path to walk.

        Yields:
            tuple: A tuple containing the directory path (str),
            a list of subdirectories (list of str), and a
            list of files (list of str).

        Example:
            ssh = MagicSSH(...)
            for dirpath, dirnames, filenames in ssh.sftp_walk(path):
                # etc
        """
        dirs = []
        files = []

        sftp = self.client.sftp()

        for i in sftp.listdir_attr(path):
            if stat.S_ISDIR(i.st_mode):
                dirs.append(i.filename)
            else:
                files.append(i.filename)

        yield path, dirs, files

        for d in dirs:
            for i in self.sftp_walk(
                posixpath.join(path, d)
            ):
                yield i

    def sftp_path_exists(self, remote: str) -> bool:
        """Check if a path exists on the remote system using SFTP.

        Args:
            remote: Path to test on the remote system.

        Returns:
            True if the file exists, False otherwise.
        """
        try:
            sftp = self.client.sftp()
            sftp.stat(remote)
            return True
        except FileNotFoundError:
            return False

    def sftp_makedirs(self, remote: str) -> None:
        """Recursively make directories on the remote system using SFTP.

        This will safely create any sub-directories, even if their
        parents do not exist.

        Args:
            remote: Directories on the remote system.

        Returns:
            None
        """
        sftp = self.client.sftp()
        remote = sftp.normalize(remote)

        dir_list = []

        # Recurse up the directory tree until we find an existing parent.
        while not self.sftp_path_exists(remote):
            # Save the child dir for later.
            dir_list.append(os.path.basename(remote))
            remote = os.path.dirname(remote)

        # Order is backwards so reverse it to match the order provided.
        dir_list.reverse()

        for i in dir_list:
            # Path is posix so we expect forward path separators.
            # os.path.join() can work here too but will change depending
            # on host OS.
            remote += f'/{i}'
            # Normalize the path to ensure it is correctly formatted.
            remote = sftp.normalize(remote)
            sftp.mkdir(remote)
