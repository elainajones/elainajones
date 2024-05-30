from fabric import Connection

class SSHSession:
    def __init__(self, host, user, password=None, identity_file=None):
        if password:
            self.session = Connection(
                host=host,
                user=user,
                connect_kwargs={
                    "password": password,
                },
            )
        elif identity_file:
            self.session = Connection(
                host=host,
                user=user,
                connect_kwargs={
                    "key_filename": identity_file,
                    "look_for_keys": False,
                },
            )
    def close(self):
        self.session.close()

    def put(self, local, remote=None):
        self.session.put(local=local, remote=remote)

    def get(self, remote, local=None):
        self.session.get(remote=remote, local=local)

    def run(self, cmd):
        result = self.session.run(cmd)

        return result
        
