#!/usr/bin/env python3
"""
smtpserver.py -d <domains> -s <mail-storage> -p <port>
"""

import sys
import argparse
import json
import time
import hashlib
from pathlib import Path
from email import message_from_bytes
from datetime import datetime
from io import BytesIO

from twisted.internet import reactor, defer, ssl
from twisted.mail import smtp
from twisted.mail.smtp import ESMTP
from twisted.internet.protocol import Factory
from zope.interface import implementer

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class MessageStorage:
    def __init__(self, mail_storage, domains):
        self.mail_storage = Path(mail_storage)
        self.domains = domains
        self.mail_storage.mkdir(parents=True, exist_ok=True)

    def save_message(self, recipient, message_data):
        try:
            msg = message_from_bytes(message_data)
            from_addr = msg.get('From', 'unknown')
            subject = msg.get('Subject', 'Sin asunto')
            date = msg.get('Date', datetime.now().isoformat())

            # Detectar adjuntos MIME
            attachments = []
            if msg.is_multipart():
                for part in msg.walk():
                    cd = part.get('Content-Disposition', '')
                    if 'attachment' in cd:
                        fname = part.get_filename() or 'adjunto'
                        attachments.append(fname)

            recipient_user = recipient.lower().replace('@', '_at_').replace('<', '').replace('>', '')
            user_dir = self.mail_storage / recipient_user / "inbox"
            user_dir.mkdir(parents=True, exist_ok=True)

            msg_id = hashlib.md5(f"{recipient}{from_addr}{time.time()}".encode()).hexdigest()[:8]

            with open(user_dir / f"{msg_id}.eml", 'wb') as f:
                f.write(message_data)

            metadata = {
                "id": msg_id,
                "from": from_addr,
                "to": recipient,
                "subject": subject,
                "date": date,
                "read": False,
                "size": len(message_data),
                "timestamp": time.time(),
                "attachments": attachments,
                "multipart": msg.is_multipart()
            }

            with open(user_dir / f"{msg_id}.json", 'w') as f:
                json.dump(metadata, f, indent=2)

            print(f"📧 Guardado: {msg_id}.eml | De: {from_addr} | Asunto: {subject}")
            if attachments:
                print(f"   📎 Adjuntos: {', '.join(attachments)}")
            return True

        except Exception as e:
            print(f"❌ Error guardando: {e}")
            return False


@implementer(smtp.IMessage)
class MailMessage:
    def __init__(self, recipient, storage):
        self.recipient = recipient
        self.storage = storage
        self.lines = []

    def lineReceived(self, line):
        if isinstance(line, str):
            line = line.encode('utf-8')
        self.lines.append(line)

    def eomReceived(self):
        print(f"📨 Mensaje completo ({len(self.lines)} líneas)")
        message_data = b'\n'.join(self.lines)
        self.storage.save_message(self.recipient, message_data)
        self.lines = []
        return defer.succeed(None)

    def connectionLost(self):
        print("⚠️ Conexión perdida antes de completar")
        self.lines = []


@implementer(smtp.IMessageDelivery)
class MailDelivery:
    def __init__(self, domains, storage):
        self.domains = domains
        self.storage = storage

    def receivedHeader(self, helo, origin, recipients):
        return f"Received: from {helo[0]} by mail.klob.me with ESMTP"

    def validateFrom(self, helo, origin):
        print(f"📤 FROM: {origin}")
        return origin

    def validateTo(self, user):
        domain = user.dest.domain
        if isinstance(domain, bytes):
            domain = domain.decode()
        domain = domain.lower()

        local = user.dest.local
        if isinstance(local, bytes):
            local = local.decode()

        recipient = f"{local}@{domain}"
        print(f"📥 TO: {recipient} (dominio: {domain})")

        if domain in self.domains:
            print(f"✅ Dominio aceptado: {domain}")
            return lambda: MailMessage(recipient, self.storage)
        else:
            print(f"❌ Dominio rechazado: {domain}")
            raise smtp.SMTPBadRcpt(user)


class CustomSMTPFactory(Factory):
    protocol = ESMTP

    def __init__(self, domains, mail_storage):
        self.domains = domains
        self.storage = MessageStorage(mail_storage, domains)

    def buildProtocol(self, addr):
        p = self.protocol()
        p.factory = self
        p.delivery = MailDelivery(self.domains, self.storage)
        return p


def main():
    parser = argparse.ArgumentParser(description="Servidor SMTP con Twisted")
    parser.add_argument("-d", "--domains", required=True)
    parser.add_argument("-s", "--mail-storage", required=True)
    parser.add_argument("-p", "--port", type=int, default=2525)
    parser.add_argument("--tls", action="store_true", help="Activar TLS/SSL")
    parser.add_argument("--cert", default="certs/server.crt")
    parser.add_argument("--key", default="certs/server.key")
    args = parser.parse_args()

    domains = [d.strip().lower() for d in args.domains.split(',')]

    print("=" * 60)
    print("📧 SMTP SERVER - klob.me")
    print("=" * 60)
    print(f"Dominios: {domains}")
    print(f"Storage:  {args.mail_storage}")
    print(f"Puerto:   {args.port}")
    print(f"TLS:      {'✅' if args.tls else '❌ (usar --tls para activar)'}")
    print("=" * 60)

    Path(args.mail_storage).mkdir(parents=True, exist_ok=True)
    factory = CustomSMTPFactory(domains, args.mail_storage)

    if args.tls:
        ctx = ssl.DefaultOpenSSLContextFactory(args.key, args.cert)
        reactor.listenSSL(args.port, factory, ctx)
        print(f"✅ Escuchando con TLS en puerto {args.port}")
    else:
        reactor.listenTCP(args.port, factory)
        print(f"✅ Escuchando en puerto {args.port} (sin TLS)")

    reactor.run()


if __name__ == "__main__":
    main()
