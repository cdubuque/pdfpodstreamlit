# Working
import streamlit as st
import pdfplumber
from openai import OpenAI
from pathlib import Path
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, generate_blob_sas, BlobSasPermissions,ContentSettings
import re
from datetime import datetime
from datetime import timezone
from datetime import timedelta
import requests
import json
import google.generativeai as genai
import streamlit.components.v1 as components

# Initialize session state variables
if 'podcast_generated' not in st.session_state:
    st.session_state.podcast_generated = False
if 'podcast_script' not in st.session_state:
    st.session_state.podcast_script = ""
if 'podcast_title' not in st.session_state:
    st.session_state.podcast_title = ""
if 'podcast_description' not in st.session_state:
    st.session_state.podcast_description = ""
if 'short_audio_url' not in st.session_state:
    st.session_state.short_audio_url = ""
if 'audio_file_path' not in st.session_state:
    st.session_state.audio_file_path = ""

system_prompt = "Hello ChatGPT, adopt to persona of a podcast host that creates 8 to 12 minutes podcast episodes summarizing research papers. I have a PDF of a research paper. I would like you to generate a concise summary of this paper for a podcast episode of the podcast pdfPod. The target audience of the podcast is well-versed in technology and computer science, but not necessarily in the specific area covered by the paper. Please focus on the following in your summary: Key concepts and technologies introduced in the paper. Any innovative methods or findings. Implications of the research and its practical applications. Future directions mentioned in the research or potential impact on the field. Aim for the summary to be engaging and accessible, providing explanations of technical terms and concepts to ensure clarity. Please keep your summary informative and go into detail on any key topics covered. Each episode is standalone, so please don't tell them to stay tuned for updates. Format it as a plain text verbatim script of the explanation. Do not include titles, sections titles, or any other unnecesary text content. The output must be at least 1000 words."

# Set your OpenAI API key
client = OpenAI(api_key=st.secrets['OPENAI_API_KEY'])
genai.configure(api_key=st.secrets['GOOGLE_API_KEY'])

# Page title
st.set_page_config(page_title='pdfPod', page_icon='🎧')

# Introduction Section
st.title('🎧 pdfPod')
st.markdown("""
### Transform Academic Papers into Engaging Podcasts

pdfPod is an innovative tool that converts complex academic research papers into accessible audio summaries. Simply upload a PDF of your research paper, and our AI will generate an 8-12 minute podcast episode that breaks down the key concepts, findings, and implications in an engaging, easy-to-understand format.

Perfect for researchers, students, and anyone interested in staying up-to-date with the latest academic developments without spending hours reading through dense papers.
""")

with st.expander('How it works'):
    st.markdown("""
    1. **Upload**: Choose your academic paper PDF
    2. **Generate**: Our AI analyzes the content and creates a podcast script
    3. **Listen**: Preview your generated podcast episode
    4. **Publish**: Share your episode with the world on major podcast platforms
    """)

# Input Section
st.header('📄 Generate Your Podcast Summary')

col1, col2 = st.columns([1, 2])

with col1:
    model_choice = st.selectbox(
        "Choose AI model:",
        ["OpenAI", "Gemini"],
        help="Select the AI model to generate your podcast summary"
    )

with col2:
    uploaded_file = st.file_uploader(
        "Upload your academic paper (PDF)",
        type=["pdf"],
        help="Upload a PDF file of the research paper you want to summarize"
    )

# Process the uploaded file
if uploaded_file and not st.session_state.podcast_generated:
    with st.status("Generating your podcast...", expanded=True) as status:
        st.write("📖 Reading PDF contents...")
        # Read PDF contents
        with pdfplumber.open(uploaded_file) as pdf:
            pdf_text = ""
            for page in pdf.pages:
                pdf_text += page.extract_text()

        st.write("🤖 Generating podcast script...")
        # Send contents to model API for text generation
        podcast_script = ""

        if model_choice == "OpenAI":
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo-0125",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": pdf_text}
                ]
            )
            podcast_script = completion.choices[0].message.content
        else:
            model=genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=system_prompt)
            response = model.generate_content(pdf_text)
            podcast_script = response.text

        st.write("📝 Creating episode title and description...")
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

        st.write("🎙️ Converting to audio...")
        speech_file_path = Path(__file__).parent / "speech.mp3"
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=podcast_script
        )
        response.stream_to_file(speech_file_path)

        st.write("☁️ Uploading to cloud storage...")
        # AZURE BLOB STORAGE AND SAS TOKEN
        connection_string = st.secrets['AZURE_CONNECTION_STRING']
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)

        container_name = st.secrets['CONTAINER_NAME']
        container_client = blob_service_client.get_container_client(container_name)

        blob_name = re.sub('[^A-Za-z]', '', str(podcast_title))
        blob_client = container_client.get_blob_client(blob_name)
        with open(speech_file_path, "rb") as data:
            blob_client.upload_blob(data, blob_type="BlockBlob", content_settings=ContentSettings(content_type='audio/mpeg', content_disposition='attachment'))

        # Generate SAS token
        sas_token = generate_blob_sas(
            blob_service_client.account_name,
            container_name,
            blob_name,
            account_key=blob_service_client.credential.account_key,
            permission=BlobSasPermissions(read=True),           
            expiry=datetime.now(timezone.utc) + timedelta(hours=8)
        )

        blob_url_with_sas = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"

        st.write("🔗 Creating shareable link...")
        # Shorten long URL with SAS
        bitly_url = 'https://api-ssl.bitly.com/v4/shorten'
        bitly_headers = {
            'Authorization': st.secrets['BITLY_KEY'],
            'Content-Type': 'application/json',
        }

        bitly_data = {
            'group_guid': st.secrets['BITLY_GUID'],
            'domain': 'bit.ly',
            'long_url': blob_url_with_sas,
        }

        bitly_response = requests.post(bitly_url, headers=bitly_headers, data=json.dumps(bitly_data))
        short_url = bitly_response.json().get('link')

        # Store in session state
        st.session_state.podcast_script = podcast_script
        st.session_state.podcast_title = podcast_title
        st.session_state.podcast_description = podcast_description
        st.session_state.short_audio_url = short_url
        st.session_state.audio_file_path = str(speech_file_path)
        st.session_state.podcast_generated = True

        status.update(label="✅ Podcast generated successfully!", state="complete")

# Podcast Preview Section
if st.session_state.podcast_generated:
    st.header('🎧 Your Generated Podcast')
    
    # Display audio player
    if st.session_state.audio_file_path and Path(st.session_state.audio_file_path).exists():
        st.audio(st.session_state.audio_file_path)
    
    # Display episode details
    st.subheader("Episode Details")
    st.write(f"**Title:** {st.session_state.podcast_title}")
    st.write(f"**Description:** {st.session_state.podcast_description}")
    
    # Display script in expandable section
    with st.expander("View Full Podcast Script"):
        st.write(st.session_state.podcast_script)
    
    # Publish button
    st.markdown("---")
    if st.button("🚀 Publish to Buzzsprout", type="primary", use_container_width=True):
        with st.spinner("Publishing your podcast..."):
            # UPLOAD TO BUZZSPROUT API
            url = st.secrets['BUZZSPROUT_URL']
            headers = {
                'Authorization': st.secrets['BUZZSPROUT_KEY'],
                "User-Agent": "pdfPod (https://pdfpod.com)"
            }
            data = {
                'title': st.session_state.podcast_title,
                'description': st.session_state.podcast_description,
                'audio_url': st.session_state.short_audio_url,
                'private': False,
            }

            response = requests.post(url, headers=headers, data=data)

            if response.status_code == 201:
                st.success("""
                🎉 **Your podcast has been successfully published to Buzzsprout!**
                
                📻 It's available immediately on our Buzzsprout page and will populate to Spotify, Amazon Music, and Pocket Casts in the next few days.
                
                Check out the "All Episodes" section below to see your published episode!
                """)
            else:
                st.error(f"Failed to publish podcast. Error code: {response.status_code}")
                st.write("Response:", response.text)

elif not uploaded_file:
    st.info('👆 Upload a PDF file to get started!')

# All Episodes Section
st.header('🎵 Listen to All Episodes')
st.markdown("Explore all published episodes from the pdfPod podcast:")

# Embed Buzzsprout player
buzzsprout_embed = """
<div id='buzzsprout-large-player'></div>
<script type='text/javascript' charset='utf-8' src='https://www.buzzsprout.com/2352847.js?container_id=buzzsprout-large-player&player=large'></script>
"""

components.html(buzzsprout_embed, height=500)