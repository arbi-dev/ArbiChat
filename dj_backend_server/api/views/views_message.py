import requests
import json
import os
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from web.models.chatbot import Chatbot
from web.utils.common import get_session_id
from web.models.chat_histories import ChatHistory


class ChatbotResponse:
    """
    This class encapsulates a chatbot's response. It provides methods to extract the bot's reply and the source documents from
    the response.

    Attributes:
        response (dict): The chatbot's response. It is expected to be a dictionary with a 'text' key for the bot's reply and an
        optional 'sourceDocuments' key for the source documents.
    """
    def __init__(self, response):
        """
        Initializes a new instance of the ChatbotResponse class.

        Args:
            response (dict): The chatbot's response.
        """
        self.response = response

    def get_bot_reply(self):
        """
        Retrieves the bot's reply from the response.

        Returns:
            str: The bot's reply.
        """
        return self.response['text']

    def get_source_documents(self):
        """
        Retrieves the source documents from the response. If the response does not include source documents, it returns an empty list.
        @TODO: To check what is source documents should return. We need to check the response from the API and show the PDF or webURL source documents.

        Returns:
            list: The source documents, or an empty list if none are included in the response.
        """
        return self.response.get('sourceDocuments', [])


@require_GET
def init_chat(request):
    """
    This view function initializes a chat session. It retrieves the bot token from the request headers and uses it to fetch the
    corresponding chatbot from the database. If no chatbot with the given token is found, it returns a 404 error. The function
    then returns a JSON response with the chatbot's name, a placeholder logo, and empty lists for FAQs and initial questions.
    @TODO: To check what is FAQ should return or we should get out the FAQ part from the initial template.
    
    Args:
        request (HttpRequest): The HTTP request object. The bot token is expected to be in the 'X-Bot-Token' header of this request.

    Returns:
        JsonResponse: A JSON response containing the chatbot's name, a placeholder logo, and empty lists for FAQs and initial questions.
    """
    bot_token = request.headers.get('X-Bot-Token')
    bot = get_object_or_404(Chatbot, token=bot_token)

    return JsonResponse({
        "bot_name": bot.name,
        "logo": "logo",
        "faq": [],
        "initial_questions": []
    })


@csrf_exempt
@require_POST
def send_search_request(request):
    """
    This view function handles the sending of a search request to an external API. It retrieves the message and chat history from
    the POST data of the request, validates them, and sends a POST request to the external API with the message, chat history, and
    other necessary parameters. It then processes the response from the API and returns a JSON response with the bot's reply or an
    error message.

    Args:
        request (HttpRequest): The HTTP request object. The message and chat history are expected to be in the POST data of this request.

    Returns:
        JsonResponse: A JSON response containing the bot's reply if the API request was successful and the API response included a
        'text' key, an error message and a 400 status code if the message was not provided, an error message and a 500 status code
        if the API response did not include a 'text' key, or an error message and a 500 status code if an exception was raised.
    """
    try:
        # Validate the request data
        message = request.POST.get('message')
        history = request.POST.getlist('history[]')

        # Implement the equivalent logic for validation
        if not message:
            return JsonResponse({
                'ai_response': "Message is required."
            }, status=400)
        # You can add additional validation for 'history' if needed.

        bot_token = request.headers.get('X-Bot-Token')
        bot = get_object_or_404(Chatbot, token=bot_token)

        # Implement the equivalent logic to send the HTTP request to the external API
        # print(os.getenv('APP_URL'))
        response = requests.post(
            os.getenv('APP_URL') + '/api/chat/',
            json={
                'question': message,
                'namespace': str(bot.id),  # Assuming getId returns a UUID object
                'mode': "assistant",
                'initial_prompt': bot.prompt_message,
                'history': history  # Assuming the API expects the chat history
            },
            timeout=200
        )

        response_json = response.json()
        if 'text' in response_json:
            bot_response = ChatbotResponse(response_json)
            return JsonResponse({
                'ai_response': bot_response.get_bot_reply()
            })
        else:
            return JsonResponse({'error': 'Unexpected response from API'}, status=500)

    except Exception as e:
        # @TODO: Log the exception into database.
        return JsonResponse({
            'ai_response': "Something went wrong, please try again later. If this issue persists, please contact support."
        }, status=500)


@csrf_exempt
@require_POST
def send_chat(request):
    """
    This view function handles the sending of a chat message to an external API. It retrieves the message, chat history, and content
    type from the POST data of the request, validates them, and sends a POST request to the external API with the message, chat history,
    content type, and other necessary parameters. It then processes the response from the API and returns a JSON response with the bot's
    reply or an error message.

    Args:
        request (HttpRequest): The HTTP request object. The message, chat history, and content type are expected to be in the POST data
        of this request.

    Returns:
        JsonResponse: A JSON response containing the bot's reply if the API request was successful and the API response included a
        'text' key, an error message and a 400 status code if the message was not provided, an error message and a 500 status code
        if the API response did not include a 'text' key, or an error message and a 500 status code if an exception was raised.
    """
    try:
        # You can add additional validation for 'history' and 'content_type' if needed.

        bot_token = request.headers.get('X-Bot-Token')
        bot = get_object_or_404(Chatbot, token=bot_token)

        data = json.loads(request.body)
        # Validate the request data
        content = data.get('content')
        history = data.get('history')
        # content_type = data.get('type')

        session_id = get_session_id(request=request, bot_id=bot.id)
        history = ChatHistory.objects.filter(session_id=session_id)
        history_entries = [{"message": entry.message, "from_user": entry.from_user} for entry in history]

        # Implement the equivalent logic for validation
        if not content:
            return JsonResponse({
                "type": "text",
                "response": {
                    "text": "Content is required."
                }
            }, status=400)

        # Implement the equivalent logic to send the HTTP request to the external API
        # print(os.getenv('APP_URL'))
        response = requests.post(
            os.getenv('APP_URL') + '/api/chat/',
            json={
                'question': content,
                'namespace': str(bot.id),  # Assuming getId returns a UUID object
                'mode': "assistant",
                'initial_prompt': bot.prompt_message,
                'history': history_entries,
                'token': bot_token,
                "session_id": session_id
            },
            timeout=200
        )
        # print(f"Response in JSON {response.json()}")

        """
        This block will first check if the response content is not empty. If it is empty, 
        it will return a JsonResponse with an error message. If the content is not empty, it will try to decode the JSON. If there is
        a JSONDecodeError, it will catch the exception and return a JsonResponse with an error message.
        """
        if not response.content:
            return JsonResponse({
                "type": "text",
                "response": {
                    "text": "The request was received successfully, but the LLM server was unable to handle it, please make sure your env keys are set correctly. **code: llm5XX**"
                }
            })
        else:
            try:
                response_json = response.json()
            except json.JSONDecodeError:
                return JsonResponse({
                    "type": "text",
                    "response": {
                        "text": "The request was received successfully, but the LLM server was unable to handle it, please make sure your env keys are set correctly. **code: llm5XX**"
                    }
                })

        bot_response = ChatbotResponse(response.json())

        return JsonResponse({
            "type": "text",
            "response": {
                "text": bot_response.get_bot_reply()
            }
        })

    except Exception as e:
        # @TODO: Log the exception into database.
        import traceback
        print(e)
        traceback.print_exc()
        return JsonResponse({
            "type": "text",
            "response": {
                "text": "I'm unable to help you at the moment, please try again later.  **code: b404**"
            }
        }, status=500)