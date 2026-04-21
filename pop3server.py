#!/usr/bin/env python3
"""
Servidor POP3 con Twisted
pop3server.py -s <mail-storage> -p <port>
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from twisted.internet import reactor, defer
from twisted.mail import pop3
from twisted.internet.protocol import Factory
from zope.interface import implementer


@implementer(pop3.IMailbox)
class Mailbox:
    """Representa el buzón de un usuario"""

    def __init__(self, user_dir):
        self.user_dir = Path(user_dir)
        self.messages = self._load_messages()
        self.deleted = set()

    def _load_messages(self):
        """Carga lista de mensajes .eml del inbox"""
        inbox = self.user_dir / "inbox"
        if not inbox.exists():
            return []
        return sorted(inbox.glob("*.eml"))

    def listMessages(self, index=None):
        """Retorna tamaños de mensajes"""
        if index is not None:
            if index in self.deleted:
                return defer.fail(pop3.MessageDeleted())
            size = self.messages[index].stat().st_size
            return defer.succeed(size)
        sizes = []
        for i, msg_path in enumerate(self.messages):
            if i not in self.deleted:
                sizes.append(msg_path.stat().st_size)
            else:
                sizes.append(0)
        return defer.succeed(sizes)

    def getMessage(self, index):
        """Retorna el contenido de un mensaje"""
        if index in self.deleted:
            return defer.fail(pop3.MessageDeleted())
        msg_path = self.messages[index]
        from io import BytesIO
        with open(msg_path, 'rb') as f:
            return defer.succeed(BytesIO(f.read()))

    def getUidl(self, index):
        """Retorna ID único del mensaje"""
        if index in self.deleted:
            return defer.fail(pop3.MessageDeleted())
        return defer.succeed(self.messages[index].stem)

    def deleteMessage(self, index):
        """Marca mensaje para borrar"""
        self.deleted.add(index)
        return defer.succeed(None)

    def undeleteMessages(self):
        """Cancela borrados (RSET)"""
        self.deleted.clear()
        return defer.succeed(None)

    def sync(self):
        """Aplica borrados al hacer QUIT"""
        for index in self.deleted:
            try:
                self.messages[index].unlink()
                # Borrar también el .json de metadata si existe
                json_path = self.messages[index].with_suffix('.json')
                if json_path.exists():
                    json_path.unlink()
            except Exception as e:
                print(f"⚠️ Error borrando mensaje {index}: {e}")
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
    """Servidor POP3 con autenticación simple"""

    def authenticateUserPass(self, user, password):
        """
        Autenticación básica.
        Usuario = parte local del email (ej: 'usuario' para usuario@klob.me)
        Contraseña = cualquiera por ahora (puedes agregar un users.json)
        """
        user_str = user.decode() if isinstance(user, bytes) else user
        print(f"🔐 Login: {user_str}")

        # Buscar carpeta del usuario en storage
        # Formato guardado: usuario_at_klob.me
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
        mailbox = Mailbox(user_dir)
        return defer.succeed(mailbox)


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
    parser.add_argument("-s", "--mail-storage", required=True,
                        help="Directorio de almacenamiento de correos")
    parser.add_argument("-p", "--port", type=int, default=1100,
                        help="Puerto POP3 (default: 1100)")
    args = parser.parse_args()

    print("=" * 60)
    print("📬 SERVIDOR POP3 CON TWISTED")
    print("=" * 60)
    print(f"💾 Almacenamiento: {args.mail_storage}")
    print(f"🔌 Puerto: {args.port}")
    print("=" * 60)

    factory = POP3Factory(args.mail_storage)
    reactor.listenTCP(args.port, factory)
    print(f"\n✅ Servidor POP3 corriendo en puerto {args.port}")
    print("Presiona Ctrl+C para detener\n")
    reactor.run()


if __name__ == "__main__":
    main()
