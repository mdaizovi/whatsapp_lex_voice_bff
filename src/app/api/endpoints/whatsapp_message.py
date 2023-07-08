import logging
import json
from pydub import AudioSegment
from fastapi import APIRouter, Request, Depends

from twilio.rest import Client as TwilioClient

# Internal imports
from utils import convert_audio
from settings import settings

from dependencies import get_twilio_client, get_lex_client
from consts import WhatsappInputType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# TODO: change to
# recognize_utterance - can be text or speech
# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/lexv2-runtime/client/recognize_utterance.html


@router.post("/message/whatsapp")
async def whatsapp_message(
    request: Request,
    twilio_client: TwilioClient = Depends(get_twilio_client),
    boto3_client=Depends(get_lex_client),
):
    # https://stackoverflow.com/questions/61872923/supporting-both-form-and-json-encoded-bodys-with-fastapi
    # form_data = await request.form()
    form_data = {**await request.form()}
    input_type = _get_input_type(form_data=form_data)
    whatsapp_user_number = form_data["From"].split("whatsapp:")[-1]

    lex_response = _send_input_to_lex2(boto3_client, form_data, input_type)
    if input_type == WhatsappInputType.TEXT:
        prettified = json.dumps(lex_response, indent=4)
        # print(f"\n\lex_response\n{prettified}\n")

        try:
            response_text = lex_response["messages"][0]["content"]
            _send_whatsapp_message(
                twilio_client=twilio_client,
                to_number=whatsapp_user_number,
                body_text=response_text,
            )
        except KeyError:
            # This is when Lex doesn't send messages bc it's done.
            # maybe if we add a finsihed message won't get KeyError?
            pass
    elif input_type == WhatsappInputType.AUDIO:
        print("input type is audio")
        audio_stream = lex_response["ResponseMetadata"]["audioStream"]
        media_url = _convert_lex_audio_stream_to_media_url(audio_stream)
        _send_whatsapp_message(
            twilio_client=twilio_client,
            to_number=whatsapp_user_number,
            media_url=media_url,
        )

    return


def _convert_lex_audio_stream_to_media_url(audio_stream):
    # TODO make this work, receive file and download and serve it somewhre, return url
    pass
    # audio_bytes = audio_stream.read()
    # audio_segment = AudioSegment.from_file_using_temporary_files(audio_bytes)
    # output_file_path = 'output.wav'
    # output_format = 'wav'
    # audio_segment.export(output_file_path, format=output_format)
    # try:
    #     prettified = json.dumps(lex_response, indent=4)
    #     print(f"\n\nlex_response\n{prettified}\n")
    # except:
    #     print(type(lex_response))
    #     print(lex_response)


def _send_whatsapp_message(twilio_client, to_number, body_text=None, media_url=None):
    twilio_number = settings.TWILIO_NUMBER
    twilio_kwargs = {
        "from_": f"whatsapp:{twilio_number}",
        "to": f"whatsapp:{to_number}",
    }
    if all([body_text is not None, media_url is None]):
        message_type = "text"
        twilio_kwargs["body"] = body_text
    elif all([body_text is None, media_url is not None]):
        message_type = "audio"
        twilio_kwargs["media_url"] = [
            "https://www.learningcontainer.com/wp-content/uploads/2020/02/Kalimba.mp3"
        ]
        # twilio_kwargs["media_url"] = [media_url]
    try:
        twilio_client.messages.create(**twilio_kwargs)
    except Exception as e:
        print(f"error sending {message_type} message {e}")


def _send_input_to_lex2(boto3_client, form_data, input_type):
    LOCALE_ID = _get_language()
    # TODO is this good enough, using phone number as session id?
    whatsapp_session_id = _build_session_from_whatsapp_from_value(form_data["From"])
    lex_kwargs = {
        "botId": settings.LEX2_BOT_ID,
        "botAliasId": settings.LEX2_BOT_ALIAS_ID,
        "localeId": LOCALE_ID,
        "sessionId": whatsapp_session_id,
    }

    if input_type == WhatsappInputType.TEXT:
        lex_kwargs["text"] = form_data["Body"]
        return boto3_client.recognize_text(**lex_kwargs)
    elif input_type == WhatsappInputType.AUDIO:
        # TODO remember to delete audio file after
        media_url = form_data["MediaUrl0"]
        mp3_file_path = convert_audio(audio_url=media_url)
        with open(mp3_file_path, "rb") as audio_file:
            lex_kwargs["requestContentType"] = "audio/l16; rate=16000; channels=1"
            lex_kwargs["responseContentType"] = "audio/pcm"
            lex_kwargs["inputStream"] = audio_file
            return boto3_client.recognize_utterance(**lex_kwargs)


def _build_session_from_whatsapp_from_value(from_value):
    return from_value.replace("+", "")


def _get_input_type(form_data):
    body = form_data["Body"]
    if body != "":
        return WhatsappInputType.TEXT
    else:
        # ('MediaContentType0', 'audio/ogg'),  ('NumMedia', '1'),  ('Body', '')
        return WhatsappInputType.AUDIO


def _get_language():
    # TODO get it from user input
    return "en_US"
