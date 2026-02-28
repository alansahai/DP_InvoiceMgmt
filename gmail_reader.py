import base64
import streamlit as st
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def authenticate_gmail():

    client_config = {
        "web": {
            "client_id": st.secrets["gmail"]["web"]["client_id"],
            "client_secret": st.secrets["gmail"]["web"]["client_secret"],
            "auth_uri": st.secrets["gmail"]["web"]["auth_uri"],
            "token_uri": st.secrets["gmail"]["web"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["gmail"]["web"]["auth_provider_x509_cert_url"],
            "redirect_uris": st.secrets["gmail"]["web"]["redirect_uris"],
        }
    }

    # If already authenticated, reuse credentials
    if "credentials" in st.session_state:
        creds = st.session_state["credentials"]
        return build("gmail", "v1", credentials=creds)

    # Create flow only once and store it
    if "flow" not in st.session_state:
        flow = Flow.from_client_config(client_config, SCOPES)
        flow.redirect_uri = st.secrets["gmail"]["web"]["redirect_uris"][0]
        st.session_state["flow"] = flow
    else:
        flow = st.session_state["flow"]

    query_params = st.query_params

    # 🔥 Handle redirect from Google
    if "code" in query_params:
        try:
            flow.fetch_token(code=query_params["code"])
            credentials = flow.credentials
            st.session_state["credentials"] = credentials

            # Cleanup
            st.query_params.clear()
            del st.session_state["flow"]

            return build("gmail", "v1", credentials=credentials)

        except Exception as e:
            st.error("FULL GOOGLE ERROR:")
            st.write(str(e))
            st.stop()

    # If not authenticated → show login link
    auth_url, _ = flow.authorization_url(prompt="consent")
    st.markdown(f"[Click here to authenticate Gmail]({auth_url})")
    st.stop()


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
                attachment_id = part['body'].get('attachmentId')

                if attachment_id:
                    attachment = service.users().messages().attachments().get(
                        userId='me',
                        messageId=msg['id'],
                        id=attachment_id
                    ).execute()

                    file_data = base64.urlsafe_b64decode(
                        attachment['data']
                    )

                    invoices.append((filename, file_data))

    return invoices
