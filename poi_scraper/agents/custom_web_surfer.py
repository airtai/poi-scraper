from typing import Any, Optional

from autogen.agentchat.chat import ChatResult
from fastagency.runtimes.autogen.tools import WebSurferTool

from poi_scraper.poi_types import CustomWebSurferAnswer


class CustomWebSurferTool(WebSurferTool):  # type: ignore[misc]
    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the CustomWebSurferTool with the given arguments.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(*args, **kwargs)

    @property
    def system_message(self) -> str:
        return (
            """You are responsible for guiding the web_surfer agent to extract data from a webpage.
The web_surfer agent can:

    - Click on links (e.g., “Click the 'Getting Started' link”).
    - Scroll the page to reveal more content (e.g., “Scroll down”).
    - Scrape visible content from the webpage.

Your goal is to collect:

    - Points of Interest (POIs): Specific places like landmarks, attractions, or destinations.
    - URLs with relevance scores: Links found on the webpage, scored based on their likelihood of leading to more POIs.

Step-by-Step Instructions:

General Guidelines:
    - You MUST scrape the entire webpage before anything else. This is non-negotiable and failure to do so will result in a penalty.
    - Do not click on links or navigate to other pages; focus on the current page only.
    - Do not use web searching for gathering information. We are only interested in the content of the provided webpage.
    - If you encounter a 40x error, retry the page several times before giving up.

POI Collection:
    - Look for POIs (specific places) on the page. Make sure you visit the entire page to find all POIs. This is non-negotiable and you will be penalized if you do not do so.
    - For each POI, gather:
        - Name: The name of the POI.
        - Location: The location of the POI (e.g., city or region).
        - Category: The type of POI (e.g., Beach, Temple, Museum).
        - Description: A short summary of the POI.

    - Format the POI data as a JSON object. Example:
        {
        "name": "Marina Beach",
        "location": "Chennai",
        "category": "Beach",
        "description": "Marina Beach is a natural urban beach in Chennai, Tamil Nadu, India, along the Bay of Bengal. It is the longest natural urban beach in India."
        }
    - If no POI data is available, return: "The page does not contain any POI information."

URL Collection:
    - For each URL on the page, assign a relevance score (1-5):
        - 5: Highly likely to lead to more POIs (e.g., "places," "activities," "landmarks").
        - 1: Unlikely to lead to POIs (e.g., "contact-us," "privacy-policy").
    - Provide the URLs and scores as a dictionary. Example:
        {
            "https://www.kayak.co.in/Chennai.13827.guide/places" : 5,
            "https://www.kayak.co.in/Chennai.13827.guide/activities" : 5,
            "https://www.kayak.co.in/Chennai.13827.guide/hotels/Taj-Coromandel" : 5,
            "https://www.kayak.co.in/Chennai.13827.guide/nightlife" : 5,
            "https://www.kayak.co.in/Chennai.13827.guide/food" : 4,
            "https://www.kayak.co.in/Chennai.13827.guide/contact-us" : 2,
            "https://www.kayak.co.in/Chennai.13827.guide/transport" : 3,
            "https://www.kayak.co.in/Chennai.13827.guide/about-us" : 2,
            "https://www.kayak.co.in/Chennai.13827.guide/privacy-policy" : 1,
            "https://www.kayak.co.in/Chennai.13827.guide/faq" : 1
        }

Final Output:
    Return a single JSON object with:

        - Task: A description of the task.
        - is_successful: Boolean indicating if the task was completed successfully.
        - pois_found: A list of POIs collected from the page.
        - urls_found: A dictionary of URLs and their relevance scores.
"""
            + f"""An example of the JSON-encoded summary:
{self.example_answer.model_dump_json()}

Common Mistakes to Avoid:
    - Do not include any additional text or formatting in the final JSON output.
    - Do not consider general sections like "Explore Chennai" or "Things to Do" as POIs. Only specific names like "Marina Beach" or "Kapaleeshwarar Temple" qualify.
"""
        )

    @property
    def initial_message(self) -> str:
        return f"""We are tasked with the following task: {self.task}"""

    @property
    def error_message(self) -> str:
        return f"""Please output the JSON-encoded answer only in the following format before trying to terminate the chat.

IMPORTANT:
  - NEVER enclose JSON-encoded answer in any other text or formatting including '```json' ... '```' or similar!

EXAMPLE:

{self.example_answer.model_dump_json()}

NEGATIVE EXAMPLES:

1. Do NOT include 'TERMINATE' in the same message as the JSON-encoded answer!

{self.example_answer.model_dump_json()}

TERMINATE

2. Do NOT include triple backticks or similar!

```json
{self.example_answer.model_dump_json()}
```

THE LAST ERROR MESSAGE:

{self.last_is_termination_msg_error}
"""

    def is_termination_msg(self, msg: dict[str, Any]) -> bool:
        try:
            CustomWebSurferAnswer.model_validate_json(msg["content"])
            return True
        except Exception as e:
            self.last_is_termination_msg_error = str(e)
            return False

    def _get_error_message(self, chat_result: ChatResult) -> Optional[str]:
        messages = [msg["content"] for msg in chat_result.chat_history]
        last_message = messages[-1]

        try:
            CustomWebSurferAnswer.model_validate_json(last_message)
        except Exception:
            return self.error_message

        return None

    def _get_answer(self, chat_result: ChatResult) -> CustomWebSurferAnswer:
        messages = [msg["content"] for msg in chat_result.chat_history]
        last_message = messages[-1]
        return CustomWebSurferAnswer.model_validate_json(last_message)

    def _chat_with_websurfer(
        self, message: str, clear_history: bool, **kwargs: Any
    ) -> CustomWebSurferAnswer:
        msg: Optional[str] = message

        while msg is not None:
            chat_result = self.websurfer.initiate_chat(
                self.assistant,
                clear_history=clear_history,
                message=msg,
            )
            msg = self._get_error_message(chat_result)
            clear_history = False

        return self._get_answer(chat_result)

    def _get_error_from_exception(self, task: str, e: Exception) -> str:
        answer = CustomWebSurferAnswer(
            task=f"{task}. While processing the task, an error occurred: {e!s}",
            is_successful=False,
            pois_found=[],
            urls_found={},
        )

        return self.create_final_reply(task, answer)

    def create_final_reply(self, task: str, message: CustomWebSurferAnswer) -> str:
        return message.model_dump_json()

    @property
    def example_answer(self) -> CustomWebSurferAnswer:
        return CustomWebSurferAnswer.get_example_answer()
