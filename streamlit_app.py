# Working
import streamlit as st
import pdfplumber
from openai import OpenAI
from pathlib import Path
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, generate_blob_sas, BlobSasPermissions,ContentSettings
import re
import datetime
from datetime import timezone
from datetime import timedelta
import requests
import json

# Set your OpenAI API key
client = OpenAI(api_key=st.secrets['OPENAI_API_KEY'])

# Page title
st.set_page_config(page_title='pdfPod', page_icon='🤖')
st.title('🤖 pdfPod')

with st.expander('About this app'):
    # Your app description here
    "Use pdfPod to synthesize your research paper pdfs into podcasts."

# Load data
st.header('1.1. Input data')

st.markdown('**1. Upload PDF file**')
uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])

# Initiate the model building process
if uploaded_file:
    with st.status("Running ...", expanded=True) as status:
        # Read PDF contents
        with pdfplumber.open(uploaded_file) as pdf:
            pdf_text = ""
            for page in pdf.pages:
                pdf_text += page.extract_text()

        # Send contents to OpenAI API for text generation
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": "Hello ChatGPT, I have a PDF of a research paper. I would like you to generate a concise summary of this paper for a podcast episode of the podcast TechTide. The target audience of the podcast is well-versed in technology and computer science, but not necessarily in the specific area covered by the paper. Please focus on the following in your summary: Key concepts and technologies introduced in the paper. Any innovative methods or findings. Implications of the research and its practical applications. Future directions mentioned in the research or potential impact on the field. Aim for the summary to be engaging and accessible, providing explanations of technical terms and concepts to ensure clarity. Please keep your summary concise but informative. Format it as a plain text verbatim script of the explanation. Do not include titles, sections titles, or any other unnecesary text content. The total number of characters must be less than 2000."},
                {"role": "user", "content": pdf_text}
            ]
        )

        completion_title = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": "Now generate an episode title for the following podcast script."},
                {"role": "user", "content": pdf_text}
            ]
        )

        podcast_title = completion_title.choices[0].message.content

        completion_description = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": "Now generate an episode description for the following podcast script."},
                {"role": "user", "content": pdf_text}
            ]
        )

        podcast_description = completion_description.choices[0].message.content

        speech_file_path = Path(__file__).parent / "speech.mp3"
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=completion.choices[0].message.content
        )
        response.stream_to_file(speech_file_path)

        st.audio("speech.mp3")
        # Display the generated podcast script
        st.subheader("Generated Podcast Script")
        st.write(completion.choices[0].message.content)

        # TESTING AZURE BLOB STORAGE AND SAS TOKEN

        # Create a BlobServiceClient object
        connection_string = st.secrets['AZURE_CONNECTION_STRING']
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)

        # Get a reference to the blob container
        container_name = st.secrets['CONTAINER_NAME']  # replace with your container name
        container_client = blob_service_client.get_container_client(container_name)

        # Upload the file
        blob_name = re.sub('[^A-Za-z]', '', str(podcast_title))
        blob_client = container_client.get_blob_client(blob_name)
        with open(speech_file_path, "rb") as data:
            blob_client.upload_blob(data, blob_type="BlockBlob", content_settings=ContentSettings(content_type='audio/mpeg', content_disposition='attachment'))
        print(podcast_title + "uploaded successfully.")

        # Generate SAS token
        sas_token = generate_blob_sas(
            blob_service_client.account_name,
            container_name,
            blob_name,
            account_key=blob_service_client.credential.account_key,
            permission=BlobSasPermissions(read=True),           
            expiry=datetime.datetime.now(timezone.utc) + datetime.timedelta(hours=1)  # Token valid for 1 hours
        )

        # Create a secure URL for the blob
        blob_url_with_sas = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"

        print (blob_url_with_sas)

        # Shorten long URL with SAS

        bitly_url = 'https://api-ssl.bitly.com/v4/shorten'
        bitly_headers = {
            'Authorization': st.secrets['BITLY_KEY'],
            'Content-Type': 'application/json',
        }

        # Data for the Bitly API request
        bitly_data = {
            'group_guid': st.secrets['BITLY_GUID'],
            'domain': 'bit.ly',
            'long_url': blob_url_with_sas,
        }

        # Make the request to the Bitly API
        bitly_response = requests.post(bitly_url, headers=bitly_headers, data=json.dumps(bitly_data))

        # Get the short URL from the response
        short_url = bitly_response.json().get('link')

        print (short_url)

        # UPLOAD TO BUZZSPROUT API

        # publishtime = datetime.now(timezone('US/Pacific')) + timedelta(minutes=15)

        url = st.secrets['BUZZSPROUT_URL']
        headers = {
            'Authorization': st.secrets['BUZZSPROUT_KEY'],
        }
        data = {
            'title': podcast_title,
            'description': podcast_description,
            'audio_url': short_url,
            'private': False,
            # 'published_at': publishtime
        }

        # NEED TO FIGURE OUT HOW TO GET THIS TO AUTOPUBLISH THE EPISODE
        response = requests.post(url, headers=headers, data=data)

        print(response.status_code)
        print(response.text)


else:
    st.warning('👈 Upload a PDF file to get started!')
