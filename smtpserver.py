#!/usr/bin/env python3
"""
Servidor SMTP con Twisted - Versión completamente funcional
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

from twisted.internet import reactor, defer
from twisted.mail import smtp
from twisted.mail.smtp import ESMTP
from twisted.internet.protocol import Factory
from zope.interface import implementer
from twisted.mail import imap4
from twisted.mail.smtp import IMessageDelivery

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class MessageStorage:
    """Almacena mensajes en el sistema de archivos"""

    def __init__(self, mail_storage, domains):
        self.mail_storage = Path(mail_storage)
        self.domains = domains
        self.mail_storage.mkdir(parents=True, exist_ok=True)

    def save_message(self, recipient, message_data):
        """Guarda un mensaje para un destinatario específico"""
        try:
            msg = message_from_bytes(message_data)
            from_addr = msg.get('From', 'unknown')
            subject = msg.get('Subject', 'Sin asunto')
            date = msg.get('Date', datetime.now().isoformat())

            recipient_user = recipient.lower().replace('@', '_at_')
            recipient_user = recipient_user.replace('<', '').replace('>', '')

            user_dir = self.mail_storage / recipient_user / "inbox"
            user_dir.mkdir(parents=True, exist_ok=True)

            msg_id = hashlib.md5(
                f"{recipient}{from_addr}{time.time()}".encode()
            ).hexdigest()[:8]

            msg_path = user_dir / f"{msg_id}.eml"
            with open(msg_path, 'wb') as f:
                f.write(message_data)

            metadata = {
                "id": msg_id,
                "from": from_addr,
                "to": recipient,
                "subject": subject,
                "date": date,
                "read": False,
                "size": len(message_data),
                "timestamp": time.time()
            }

            with open(user_dir / f"{msg_id}.json", 'w') as f:
                json.dump(metadata, f, indent=2)

            print(f"📧 Mensaje guardado: {msg_path}")
            print(f"   De: {from_addr}")
            print(f"   Asunto: {subject}")
            return True

        except Exception as e:
            print(f"❌ Error guardando: {e}")
            return False


@implementer(smtp.IMessage)
class MailMessage:
    """Recibe y almacena el cuerpo del mensaje"""

    def __init__(self, recipient, storage):
        self.recipient = recipient
        self.storage = storage
        self.lines = []

    def lineReceived(self, line):
        # Convertir a bytes si viene como str
        if isinstance(line, str):
            line = line.encode('utf-8')
        self.lines.append(line)

    def eomReceived(self):
        print(f"📨 Mensaje completo recibido ({len(self.lines)} líneas)")
        message_data = b'\n'.join(self.lines)
        self.storage.save_message(self.recipient, message_data)
        self.lines = []
        return defer.succeed(None)

    def connectionLost(self):
        """Conexión perdida antes de terminar"""
        print("⚠️ Conexión perdida antes de completar el mensaje")
        self.lines = []


@implementer(IMessageDelivery)
class MailDelivery:
    """Valida remitentes/destinatarios y crea el objeto mensaje"""

    def __init__(self, domains, storage):
        self.domains = domains
        self.storage = storage

    def receivedHeader(self, helo, origin, recipients):
        return f"Received: from {helo[0]} by mail.klob.me with SMTP"

    def validateFrom(self, helo, origin):
        """Acepta cualquier remitente"""
        print(f"📤 FROM: {origin}")
        return origin

    def validateTo(self, user):
        """Valida dominio del destinatario"""
        recipient_domain = user.dest.domain.decode().lower()
        recipient = f"{user.dest.local.decode()}@{recipient_domain}"
        print(f"📥 TO: {recipient} (dominio: {recipient_domain})")

        if recipient_domain in self.domains:
            print(f"✅ Dominio aceptado: {recipient_domain}")
            # Retorna un callable que produce el objeto IMessage
            return lambda: MailMessage(recipient, self.storage)
        else:
            print(f"❌ Dominio rechazado: {recipient_domain}")
            raise smtp.SMTPBadRcpt(user)


class CustomSMTPFactory(Factory):
    """Fábrica para crear instancias del servidor SMTP"""

    protocol = ESMTP

    def __init__(self, domains, mail_storage):
        self.domains = domains
        self.storage = MessageStorage(mail_storage, domains)

    def buildProtocol(self, addr):
        p = self.protocol()
        p.factory = self
        # Inyectar el delivery al protocolo
        p.delivery = MailDelivery(self.domains, self.storage)
        return p


def parse_arguments():
    parser = argparse.ArgumentParser(description="Servidor SMTP con Twisted")
    parser.add_argument("-d", "--domains", required=True,
                        help="Dominios aceptados (separados por coma)")
    parser.add_argument("-s", "--mail-storage", required=True,
                        help="Directorio para almacenar correos")
    parser.add_argument("-p", "--port", type=int, default=2525,
                        help="Puerto para SMTP (default: 2525)")
    return parser.parse_args()


def main():
    args = parse_arguments()
    domains = [d.strip().lower() for d in args.domains.split(',')]

    print("=" * 60)
    print("📧 SERVIDOR SMTP CON TWISTED")
    print("=" * 60)
    print(f"📡 Dominios aceptados: {domains}")
    print(f"💾 Almacenamiento: {args.mail_storage}")
    print(f"🔌 Puerto: {args.port}")
    print("=" * 60)

    Path(args.mail_storage).mkdir(parents=True, exist_ok=True)

    factory = CustomSMTPFactory(domains, args.mail_storage)

    try:
        reactor.listenTCP(args.port, factory)
        print(f"\n✅ Servidor SMTP corriendo en puerto {args.port}")
        print(f"📨 Prueba con: telnet localhost {args.port}\n")
        print("Presiona Ctrl+C para detener\n")
        reactor.run()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
