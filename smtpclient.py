#!/usr/bin/env python3
"""
Cliente SMTP masivo con soporte CSV
smtpclient.py -h <mail-server> -c <csv-file> -m <message-file>
"""

import argparse
import csv
import smtplib
import string
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path


def load_template(message_file):
    """Carga la plantilla del mensaje"""
    with open(message_file, 'r', encoding='utf-8') as f:
        content = f.read()
    return content


def send_email(server_host, server_port, sender, recipient, subject, body):
    """Envía un correo individual"""
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = recipient
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        with smtplib.SMTP(server_host, server_port, timeout=10) as smtp:
            smtp.ehlo()
            smtp.sendmail(sender, [recipient], msg.as_bytes())
        print(f"✅ Enviado a {recipient}")
        return True
    except Exception as e:
        print(f"❌ Error enviando a {recipient}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Cliente SMTP masivo")
    parser.add_argument("-h", "--host", required=True,
                        help="Servidor SMTP (ej: localhost o mail.klob.me)")
    parser.add_argument("-p", "--port", type=int, default=2525,
                        help="Puerto SMTP (default: 2525)")
    parser.add_argument("-c", "--csv-file", required=True,
                        help="Archivo CSV con destinatarios")
    parser.add_argument("-m", "--message-file", required=True,
                        help="Archivo con plantilla del mensaje")
    parser.add_argument("--from", dest="sender",
                        default="noreply@klob.me",
                        help="Dirección remitente")
    args = parser.parse_args()

    # Cargar plantilla
    template_text = load_template(args.message_file)

    # Leer CSV y enviar
    # El CSV debe tener columnas: email, nombre, subject, (otras variables)
    success, failed = 0, 0
    with open(args.csv_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            recipient = row.get('email', '').strip()
            if not recipient:
                continue

            # Sustituir variables en la plantilla: {{nombre}}, {{email}}, etc.
            try:
                body = template_text
                for key, value in row.items():
                    body = body.replace(f"{{{{{key}}}}}", value)

                subject = row.get('subject', 'Sin asunto')
                sent = send_email(
                    args.host, args.port,
                    args.sender, recipient,
                    subject, body
                )
                if sent:
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ Error procesando {recipient}: {e}")
                failed += 1

    print(f"\n📊 Resumen: {success} enviados, {failed} fallidos")


if __name__ == "__main__":
    main()
