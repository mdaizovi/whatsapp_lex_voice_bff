# Third-party imports
import openai

from fastapi import APIRouter, Request

# Internal imports
from utils import send_message, ogg2mp3
from settings import settings

router = APIRouter()
#TODO rewrite as deps
openai.api_key = settings.OPENAI_API_KEY


@router.post("/message/whatsapp")
async def whatsapp_message(request: Request):
    form_data = await request.form()
    whatsapp_number = form_data['From'].split("whatsapp:")[-1]
    
    # TODO convert audio with AWS, not locally.
    media_url = form_data['MediaUrl0']
    text = _get_text_from_audio_url(media_url)

    #TODO
    # send text to lex
    # return to user audio and/or text from lex

    chat_response = f"I think you said: {text}"
    send_message(whatsapp_number, chat_response)
    return ""


def _get_text_from_audio_url(media_url):
    mp3_file_path = ogg2mp3(media_url)

    with open(mp3_file_path, "rb") as audio_file:
    # Call the OpenAI API to transcribe the audio using Whisper API
        whisper_response = openai.Audio.transcribe(
            file=audio_file,
            model="whisper-1",
            language="en",
            temperature=0.5,
        )
    return whisper_response.get("text")