import json
import os.path
import smtplib
import email
from email.mime.text import MIMEText

class Notifier:

    conf = None
    real_path = ''

    def __init__(self, conf_path='~/.ssh/smtp_notify.json'):
        self.real_path = os.path.expanduser(conf_path)

    def __enter__(self):
        try:
            with open(self.real_path, 'r') as f:
                self.conf = json.load(f)
        except:
            print('Cannot open {}.'.format(self.real_path))

        return self

    def __exit__(self, type, value, traceback):
        # Show how to shoot troubles.
        return True

    def __usage(self):
        HELP = '''
        Follow steps below to config notification environment.

        $ cd ~/.ssh
        $ vim smtp_notify.json

        Copy, paste and modify this JSON into smtp_notify.json.

        {
          "host": "msa.hinet.net",
          "port": 587,
          "user": "someone",
          "pass": "somepass",
          "starttls": true,
          "debug": true,
          "from": "someone@msa.hinet.net",
          "to": "someone@gmail.com"
        }

        $ ./smtp_notify.py
        '''

    def test(self):
        self.notify('SMTP notification test.', 'It works!')

    def notify(self, subject, content):
        if not self.conf:
            raise Exception('Cannot read SMTP config.')

        conf = self.conf
        try:
            with smtplib.SMTP(conf['host'], port=conf['port'], timeout=10) as smtp:
                if conf['debug']:
                    smtp.set_debuglevel(2)
                if conf['starttls']:
                    smtp.starttls()
                smtp.login(conf['user'], conf['pass'])

                message = MIMEText(content, 'plain', 'UTF-8')
                message['Subject'] = subject
                message['From'] = conf['from']
                message['To'] = conf['to']
                payload = message.as_string()
                smtp.sendmail(conf['from'], conf['to'], payload)
        except:
            print('Cannot connect {}.'.format(conf['host']))

def main():
    with Notifier() as n:
        n.test()

if __name__ == '__main__':
    main()
