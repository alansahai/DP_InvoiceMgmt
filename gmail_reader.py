import os
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate_gmail():
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    service = build('gmail', 'v1', credentials=creds)
    return service
def read_invoice_emails():
    service = authenticate_gmail()

    results = service.users().messages().list(
        userId='me',
        q='is:unread has:attachment'
    ).execute()

    messages = results.get('messages', [])
    invoices = []

    for msg in messages:
        msg_data = service.users().messages().get(
            userId='me',
            id=msg['id']
        ).execute()

        parts = msg_data['payload'].get('parts', [])

        for part in parts:
            filename = part.get('filename')

            if filename:
                attachment_id = part['body']['attachmentId']
                attachment = service.users().messages().attachments().get(
                    userId='me',
                    messageId=msg['id'],
                    id=attachment_id
                ).execute()

                file_data = base64.urlsafe_b64decode(
                    attachment['data'])

                invoices.append((filename, file_data))

    return invoices
