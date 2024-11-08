from typing import Annotated, Any, Optional

from autogen.agentchat.chat import ChatResult

from fastagency.runtimes.autogen.tools import WebSurferTool
from pydantic import BaseModel, Field, HttpUrl


class CustomWebSurferAnswer(BaseModel):
    task: Annotated[str, Field(..., description="The task to be completed")]
    is_successful: Annotated[
        bool, Field(..., description="Whether the task was successful")
    ]
    poi_details: Annotated[
        str,
        Field(..., description="The details of all the POIs found in the webpage"),
    ]
    visited_links: Annotated[
        list[HttpUrl],
        Field(..., description="The list of visited links to generate the POI details"),
    ]

    @staticmethod
    def get_example_answer() -> "CustomWebSurferAnswer":
        return CustomWebSurferAnswer(
            task="Collect Points of Interest data from the webpage https://www.kayak.co.in/Chennai.13827.guide",
            is_successful=True,
            poi_details="Below are the list of all the POIs found in the webpage: \n\n1. Name: Marina Beach, Location: Chennai\n2. Name: Kapaleeshwarar Temple, Location: Chennai\n3. Name: Arignar Anna Zoological Park, Location: Chennai\n4. Name: Guindy National Park, Location: Chennai\n5. Name: Government Museum, Location: Chennai\n6. Name: Valluvar Kottam, Location: Chennai\n7. Name: Fort St. George, Location: Chennai\n8. Name: San Thome Church, Location: Chennai\n9. Name: Elliot\'s Beach, Location: Chennai\n10. Name: Semmozhi Poonga, Location: Chennai",
            visited_links=[
                "https://www.kayak.co.in/Chennai.13827.guide",
            ],
        )


class CustomWebSurferTool(WebSurferTool):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def system_message(self) -> str:
        return """You are in charge of navigating the web_surfer agent to scrape the web.
web_surfer is able to CLICK on links, SCROLL down, and scrape the content of the web page. e.g. you cen tell him: "Click the 'Getting Started' result".
Each time you receive a reply from web_surfer, you need to tell him what to do next. e.g. "Click the TV link" or "Scroll down".

You need to guide the web_surfer agent to gather Points of Interest (POIs) on a given webpage. Instruct the web_surfer to visit the 
specified page and scroll down until the very end to view the full content.

Follow the below instructions for collecting the POI's:

INSTRUCTIONS:
- You MUST visit the full webpage. This is non-negotiable and you will be penalized if you do not do so.
- As you scroll the webpage, collect as much POI's as possible from the given webpage.
- Do not click on any links or navigate to other pages. Focus solely on the current page.
- If the webpage has POI information, then encode the POI name, location, category and description as a JSON string. For example:
    {
        "name":"Marina Beach",
        "location":"Chennai",
        "category":"Beach",
        "description":"Marina Beach is a natural urban beach in Chennai, Tamil Nadu, India, along the Bay of Bengal. The beach runs from near Fort St. George in the north to Foreshore Estate in the south, a distance of 6.0 km (3.7 mi), making it the longest natural urban beach in the country."
    }
- Sometimes the webpages will have the category names like "Explore Chennai", "Things to do in Chennai", "Places to visit in Chennai" etc. You SHOULD NOT consider these as POIs. The POI's are the specific names like "Marina Beach", "Kapaleeshwarar Temple", "Arignar Anna Zoological Park" etc. NEVER EVER break this rule.
- If there is no POI infomation in the given page then return "The page does not contain any POI information".
- Finally summarize the findings for the given task. The summary must be in English!
- Create a summary after you have collected all the POI's from the webpage.
- If you get some 40x error, please do NOT give up immediately, but try again on the same page. Give up only if you get 40x error after multiple attempts.


Examples:
"Click the "given webpage" - This way you will navigate to the given webpage and you will find more information about the POIs.
"Scroll down" - this will get you more information about the POIs on the page.
"Register the POI" - this will get you the POI information from the page.


FINAL MESSAGE:
- Once you have retrieved all the POI's from the webpage and created the summary, you need to send the JSON-encoded summary to the web_surfer.
- You MUST not include any other text or formatting in the message, only JSON-encoded summary!

""" + f"""An example of the JSON-encoded summary:
{self.example_answer.model_dump_json()}

TERMINATION:
When YOU are finished and YOU have created JSON-encoded answer, write a single 'TERMINATE' to end the task.

OFTEN MISTAKES:
- Enclosing JSON-encoded answer in any other text or formatting including '```json' ... '```' or similar!
- Considering the category names like "Explore Chennai", "Things to do in Chennai", "Places to visit in Chennai" etc. as POIs. The POI's are the specific names like "Marina Beach", "Kapaleeshwarar Temple", "Arignar Anna Zoological Park" etc.
"""

    @property
    def initial_message(self) -> str:
        return f"""We are tasked with the following task: {self.task}"""

    def is_termination_msg(self, msg: dict[str, Any]) -> bool:
        # print(f"is_termination_msg({msg=})")
        if (
            "content" in msg
            and msg["content"] is not None
            and "TERMINATE" in msg["content"]
        ):
            return True
        try:
            CustomWebSurferAnswer.model_validate_json(msg["content"])
            return True
        except Exception as e:
            self.last_is_termination_msg_error = str(e)
            return False
        
    def _get_error_message(self, chat_result: ChatResult) -> Optional[str]:
        messages = [msg["content"] for msg in chat_result.chat_history]
        last_message = messages[-1]
        if "TERMINATE" in last_message:
            return self.error_message

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
            task=task,
            is_successful=False,
            poi_details=f"unexpected error occurred: {str(e)}",
            visited_links=[],
        )

        return self.create_final_reply(task, answer)
    
    def create_final_reply(self, task: str, message: CustomWebSurferAnswer) -> str:
        retval = (
            "We have successfully completed the task:\n\n"
            if message.is_successful
            else "We have failed to complete the task:\n\n"
        )
        retval += f"{task}\n\n"
        retval += f"poi_details: {message.poi_details}\n\n"
        retval += "Visited links:\n"
        for link in message.visited_links:
            retval += f"  - {link}\n"

        return retval
    
    @property
    def example_answer(self) -> CustomWebSurferAnswer:
        return CustomWebSurferAnswer.get_example_answer()
