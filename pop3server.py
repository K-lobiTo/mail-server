#!/usr/bin/env python3
"""
pop3server.py -s <mail-storage> -p <port>
"""

import argparse
from pathlib import Path

from twisted.internet import reactor, defer, ssl
from twisted.mail import pop3
from twisted.internet.protocol import Factory
from zope.interface import implementer


@implementer(pop3.IMailbox)
class Mailbox:
    def __init__(self, user_dir):
        self.user_dir = Path(user_dir)
        self.messages = self._load_messages()
        self.deleted = set()

    def _load_messages(self):
        inbox = self.user_dir / "inbox"
        if not inbox.exists():
            return []
        return sorted(inbox.glob("*.eml"))

    def listMessages(self, index=None):
        if index is not None:
            if index in self.deleted:
                return defer.fail(pop3.MessageDeleted())
            return defer.succeed(self.messages[index].stat().st_size)
        sizes = [
            self.messages[i].stat().st_size if i not in self.deleted else 0
            for i in range(len(self.messages))
        ]
        return defer.succeed(sizes)

    def getMessage(self, index):
        if index in self.deleted:
            return defer.fail(pop3.MessageDeleted())
        from io import BytesIO
        with open(self.messages[index], 'rb') as f:
            return defer.succeed(BytesIO(f.read()))

    def getUidl(self, index):
        if index in self.deleted:
            return defer.fail(pop3.MessageDeleted())
        return defer.succeed(self.messages[index].stem)

    def deleteMessage(self, index):
        self.deleted.add(index)
        return defer.succeed(None)

    def undeleteMessages(self):
        self.deleted.clear()
        return defer.succeed(None)

    def sync(self):
        for i in self.deleted:
            try:
                self.messages[i].unlink()
                json_p = self.messages[i].with_suffix('.json')
                if json_p.exists():
                    json_p.unlink()
            except Exception as e:
                print(f"⚠️ Error borrando mensaje {i}: {e}")
        return defer.succeed(None)

    def getMessageCount(self):
        return defer.succeed(len(self.messages) - len(self.deleted))

    def getMailboxSize(self):
        total = sum(
            p.stat().st_size for i, p in enumerate(self.messages)
            if i not in self.deleted
        )
        return defer.succeed(total)


class POP3Server(pop3.POP3):
    def authenticateUserPass(self, user, password):
        user_str = user.decode() if isinstance(user, bytes) else user
        print(f"🔐 Login: {user_str}")

        storage = self.factory.mail_storage
        user_dir = None
        for candidate in Path(storage).iterdir():
            if candidate.name.startswith(user_str + "_at_"):
                user_dir = candidate
                break

        if user_dir is None:
            print(f"❌ Usuario no encontrado: {user_str}")
            return defer.fail(pop3.LoginFailed("Usuario no encontrado"))

        print(f"✅ Autenticado: {user_str} → {user_dir}")
        return defer.succeed(Mailbox(user_dir))


class POP3Factory(Factory):
    protocol = POP3Server

    def __init__(self, mail_storage):
        self.mail_storage = mail_storage

    def buildProtocol(self, addr):
        p = self.protocol()
        p.factory = self
        return p


def main():
    parser = argparse.ArgumentParser(description="Servidor POP3 con Twisted")
    parser.add_argument("-s", "--mail-storage", required=True)
    parser.add_argument("-p", "--port", type=int, default=1100)
    parser.add_argument("--tls", action="store_true")
    parser.add_argument("--cert", default="certs/server.crt")
    parser.add_argument("--key", default="certs/server.key")
    args = parser.parse_args()

    print("=" * 60)
    print("📬 POP3 SERVER - klob.me")
    print("=" * 60)
    print(f"Storage: {args.mail_storage}")
    print(f"Puerto:  {args.port}")
    print(f"TLS:     {'✅' if args.tls else '❌'}")
    print("=" * 60)

    factory = POP3Factory(args.mail_storage)

    if args.tls:
        ctx = ssl.DefaultOpenSSLContextFactory(args.key, args.cert)
        reactor.listenSSL(args.port, factory, ctx)
        print(f"✅ POP3 con TLS en puerto {args.port}")
    else:
        reactor.listenTCP(args.port, factory)
        print(f"✅ POP3 en puerto {args.port}")

    reactor.run()


if __name__ == "__main__":
    main()
