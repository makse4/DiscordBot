from openai import OpenAI
from dotenv import load_dotenv
import os
from ast import literal_eval

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI()

def smart_add(search_term, number_of_songs):
    response = client.responses.create(
        model="gpt-3.5-mini",
        input=f"Generate a list of {number_of_songs} songs related to '{search_term}'. Provide only the song titles in a python list format.",
    )
    return literal_eval(response.output_text)
