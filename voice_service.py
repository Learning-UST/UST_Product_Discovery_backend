import azure.cognitiveservices.speech as speechsdk
import string
from config import get_config_value

def transcribe_audio(audio_file_path):
    speech_config = speechsdk.SpeechConfig(
        subscription=get_config_value("AZURE_SPEECH_KEY"), 
        region=get_config_value("AZURE_SPEECH_REGION")
    )
    audio_config = speechsdk.audio.AudioConfig(filename=audio_file_path)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    result = speech_recognizer.recognize_once_async().get()
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text.strip().rstrip(string.punctuation)
    return None