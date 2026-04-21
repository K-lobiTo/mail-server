#!/usr/bin/env python3
"""
Notificador XMPP - alerta cuando llega un nuevo correo
Se integra con el SMTP server monitoreando el storage
"""

import asyncio
import argparse
import time
from pathlib import Path
import slixmpp


class MailNotifier(slixmpp.ClientXMPP):
    """Cliente XMPP que notifica nuevos correos"""

    def __init__(self, jid, password, notify_jid, mail_storage):
        super().__init__(jid, password)
        self.notify_jid = notify_jid
        self.mail_storage = Path(mail_storage)
        self.seen_files = set()

        self.add_event_handler("session_start", self.on_connect)

    async def on_connect(self, event):
        self.send_presence()
        await self.get_roster()
        print(f"✅ XMPP conectado como {self.boundjid}")
        print(f"📡 Monitoreando: {self.mail_storage}")
        asyncio.ensure_future(self.watch_mailbox())

    async def watch_mailbox(self):
        """Monitorea el storage y notifica nuevos .eml"""
        # Inicializar con archivos existentes
        for eml in self.mail_storage.rglob("*.eml"):
            self.seen_files.add(str(eml))

        while True:
            await asyncio.sleep(5)  # revisar cada 5 segundos
            for eml in self.mail_storage.rglob("*.eml"):
                path_str = str(eml)
                if path_str not in self.seen_files:
                    self.seen_files.add(path_str)
                    await self.notify_new_mail(eml)

    async def notify_new_mail(self, eml_path):
        """Envía notificación XMPP"""
        # Leer metadata del .json si existe
        json_path = eml_path.with_suffix('.json')
        if json_path.exists():
            import json
            with open(json_path) as f:
                meta = json.load(f)
            msg_text = (
                f"📧 Nuevo correo en klob.me\n"
                f"De: {meta.get('from', '?')}\n"
                f"Para: {meta.get('to', '?')}\n"
                f"Asunto: {meta.get('subject', '?')}"
            )
        else:
            msg_text = f"📧 Nuevo correo recibido: {eml_path.name}"

        print(f"🔔 Notificando: {msg_text}")
        self.send_message(mto=self.notify_jid, mbody=msg_text, mtype='chat')


def main():
    parser = argparse.ArgumentParser(description="Notificador XMPP de correos")
    parser.add_argument("--jid", required=True,
                        help="Tu JID XMPP (ej: bot@jabber.org)")
    parser.add_argument("--password", required=True,
                        help="Contraseña XMPP")
    parser.add_argument("--notify", required=True,
                        help="JID a notificar (ej: tu@jabber.org)")
    parser.add_argument("-s", "--mail-storage", required=True,
                        help="Directorio de almacenamiento de correos")
    args = parser.parse_args()

    xmpp = MailNotifier(args.jid, args.password, args.notify, args.mail_storage)
    xmpp.connect()
    xmpp.process(forever=True)


if __name__ == "__main__":
    main()
