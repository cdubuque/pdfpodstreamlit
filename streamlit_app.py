# Working

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import time
import zipfile
import pdfplumber
from openai import OpenAI
from pathlib import Path
import pyaudio
import os

# Set your OpenAI API key
client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

# Page title
st.set_page_config(page_title='pdfPod', page_icon='🤖')
st.title('🤖 pdfPod')

with st.expander('About this app'):
    # Your app description here
    "Use me to synthesize your research paper pdfs into podcasts."

# Sidebar for accepting input parameters
with st.sidebar:
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
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Hello ChatGPT, I have a PDF of a research paper. I would like you to generate a concise summary of this paper for a podcast episode of the podcast TechTide. The target audience of the podcast is well-versed in technology and computer science, but not necessarily in the specific area covered by the paper. Please focus on the following in your summary: Key concepts and technologies introduced in the paper. Any innovative methods or findings. Implications of the research and its practical applications. Future directions mentioned in the research or potential impact on the field. Aim for the summary to be engaging and accessible, providing explanations of technical terms and concepts to ensure clarity. The duration of the podcast segment should be around ten minutes, so please keep your summary concise but informative. The total number of characters must be less than 2000."},
                {"role": "user", "content": pdf_text}
            ]
        )


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

else:
    st.warning('👈 Upload a PDF file to get started!')
