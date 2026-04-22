#!/usr/bin/env python3
"""
notifier.py --jid <bot_jid> --password <pass> --notify <user_jid> -s <mail-storage>
"""

import asyncio
import argparse
import json
import threading
from pathlib import Path

import slixmpp


class MailNotifier(slixmpp.ClientXMPP):

    def __init__(self, jid, password, notify_jid, mail_storage):
        super().__init__(jid, password)
        self.notify_jid = notify_jid
        self.mail_storage = Path(mail_storage)
        self.seen_files = set()

        self.add_event_handler("session_start", self.on_connect)
        self.add_event_handler("failed_auth", self.on_failed_auth)

    async def on_failed_auth(self, event):
        print("❌ Autenticación XMPP fallida — verifica JID y contraseña")
        self.disconnect()

    async def on_connect(self, event):
        self.send_presence()
        await self.get_roster()
        print(f"✅ XMPP conectado como {self.boundjid}")
        print(f"📡 Monitoreando: {self.mail_storage}")
        print(f"🔔 Notificando a: {self.notify_jid}")

        # Registrar archivos existentes para no notificar correos viejos
        for eml in self.mail_storage.rglob("*.eml"):
            self.seen_files.add(str(eml))
        print(f"📂 {len(self.seen_files)} correos existentes ignorados (solo nuevos serán notificados)")

        asyncio.ensure_future(self.watch_mailbox())

    async def watch_mailbox(self):
        """Monitorea el storage cada 5 segundos"""
        while True:
            await asyncio.sleep(5)
            try:
                for eml in self.mail_storage.rglob("*.eml"):
                    path_str = str(eml)
                    if path_str not in self.seen_files:
                        self.seen_files.add(path_str)
                        await self.notify_new_mail(eml)
            except Exception as e:
                print(f"⚠️ Error en watch: {e}")

    async def notify_new_mail(self, eml_path):
        """Envía notificación XMPP con detalles del correo"""
        json_path = eml_path.with_suffix('.json')
        if json_path.exists():
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

        print(f"🔔 Enviando notificación XMPP:\n{msg_text}")
        self.send_message(mto=self.notify_jid, mbody=msg_text, mtype='chat')


def main():
    parser = argparse.ArgumentParser(description="Notificador XMPP de correos")
    parser.add_argument("--jid", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--notify", required=True)
    parser.add_argument("-s", "--mail-storage", required=True)
    args = parser.parse_args()

    print("=" * 60)
    print("🔔 NOTIFICADOR XMPP")
    print("=" * 60)
    print(f"Bot JID:  {args.jid}")
    print(f"Notifica: {args.notify}")
    print(f"Storage:  {args.mail_storage}")
    print("=" * 60)

    xmpp = MailNotifier(args.jid, args.password, args.notify, args.mail_storage)
    xmpp.connect()

    # Usar el loop interno que slixmpp ya creó
    loop = xmpp.loop
    try:
        loop.run_until_complete(xmpp.disconnected)
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo notificador...")
        xmpp.disconnect()


if __name__ == "__main__":
    main()
