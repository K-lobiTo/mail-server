#!/usr/bin/env python3
"""
smtpclient.py -h <mail-server> -c <csv-file> -m <message-file>
"""

import argparse
import csv
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path


def load_template(message_file):
    with open(message_file, 'r', encoding='utf-8') as f:
        return f.read()


def build_message(sender, recipient, subject, body, attachment_path=None):
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = recipient
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    if attachment_path and Path(attachment_path).exists():
        with open(attachment_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{Path(attachment_path).name}"')
        msg.attach(part)

    return msg


def send_email(host, port, sender, recipient, subject, body,
               attachment=None, use_tls=False):
    msg = build_message(sender, recipient, subject, body, attachment)
    try:
        with smtplib.SMTP(host, port, timeout=10) as s:
            s.ehlo()
            if use_tls:
                s.starttls()
                s.ehlo()
            s.sendmail(sender, [recipient], msg.as_bytes())
        print(f"✅ Enviado → {recipient}")
        return True
    except Exception as e:
        print(f"❌ Error → {recipient}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Cliente SMTP masivo")
    # El parámetro es -h pero argparse usa -h para help, usamos --host y alias
    parser.add_argument("--host", "-H", required=True, help="Servidor SMTP")
    parser.add_argument("-p", "--port", type=int, default=2525)
    parser.add_argument("-c", "--csv-file", required=True)
    parser.add_argument("-m", "--message-file", required=True)
    parser.add_argument("--from", dest="sender", default="noreply@klob.me")
    parser.add_argument("--attachment", default=None, help="Archivo adjunto opcional")
    parser.add_argument("--tls", action="store_true")
    args = parser.parse_args()

    template = load_template(args.message_file)
    ok, fail = 0, 0

    with open(args.csv_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            recipient = row.get('email', '').strip()
            if not recipient:
                continue

            # Sustituir variables {{nombre}}, {{email}}, etc.
            body = template
            for key, val in row.items():
                body = body.replace(f"{{{{{key}}}}}", val)

            subject = row.get('subject', 'Mensaje de klob.me')

            sent = send_email(
                args.host, args.port,
                args.sender, recipient,
                subject, body,
                attachment=args.attachment,
                use_tls=args.tls
            )
            if sent:
                ok += 1
            else:
                fail += 1

    print(f"\n📊 {ok} enviados, {fail} fallidos")


if __name__ == "__main__":
    main()
