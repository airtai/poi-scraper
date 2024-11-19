from typing import Annotated, Any, Literal, Optional

from autogen.agentchat.chat import ChatResult
from fastagency.runtimes.autogen.tools import WebSurferTool
from pydantic import BaseModel, Field, HttpUrl


class CustomWebSurferAnswer(BaseModel):
    task: Annotated[str, Field(..., description="The task to be completed")]
    is_successful: Annotated[
        bool, Field(..., description="Whether the task was successful")
    ]
    decision: Annotated[
        Literal["CONTINUE", "TERMINATE"],
        Field(..., description="The decision whether to CONTINUE or TERMINATE"),
    ]
    current_url: Annotated[
        HttpUrl, Field(..., description="The URL of the current page")
    ]
    description: Annotated[str, Field(..., description="A short summary of the page")]

    @staticmethod
    def get_example_answer() -> "CustomWebSurferAnswer":
        return CustomWebSurferAnswer(
            task="Collect Points of Interest data and links with score from the webpage https://example.com",
            is_successful=True,
            decision="CONTINUE",
            current_url="https://example.com",
            description="The page contains information about tourist attractions, landmarks, parks, museums, cultural venues, and historic sites.",
        )


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
            """You are in charge of navigating the web_surfer agent to scrape the web.
web_surfer is able to CLICK on links, SCROLL down, and scrape the content of the web page. e.g. you cen tell him: "Click the 'Getting Started' result".
Each time you receive a reply from web_surfer, you need to tell him what to do next. e.g. "Click the TV link" or "Scroll down".

You need to guide the web_surfer agent to gather Points of Interest (POIs) on a given webpage. Instruct the web_surfer to visit the
specified page and scroll down until the very end to view the full content.

Guiding Examples:
    - "Click the "given webpage" - This way you will navigate to the given webpage and you will find more information about the POIs.
    - "Scroll down" - this will get you more information about the POIs on the page.
    - "Register the POI" - this will get you the POI information from the page.
    - "Register new link" - this will get you the new link information from the page.


For a given page your objective is to:
    - Collect as many POIs as possible from the given webpage.
    - Return a list of links available on that page along with a score for each link. The score be in the range of 1 to 5. The score should be based on the likelihood that the link will lead to more POIs collections.

Follow the below instructions for collecting the POI's and new links from the webpage:

GENERAL INSTRUCTIONS:
- You MUST visit the full webpage. This is non-negotiable and you will be penalized if you do not do so.
- As you scroll the webpage, collect as much POI's as possible from the given webpage.
- Do not click on any links or navigate to other pages. Focus solely on the current page.
- Create a summary after you have collected all the POI's from the webpage.  The summary must be in English!
- If you get some 40x error, please do NOT give up immediately, but try again on the same page. Give up only if you get 40x error after multiple attempts.
- NEVER call `register_poi` and `register_new_link` without visiting the full webpage. This is a very important instruction and you will be penalised if you do so.
- After visiting the webpage and identifying the POIs, you MUST call the `register_poi` function to record the POI.
- If you find any new links on the webpage, you can call the `register_new_link` function to record the link along with the score (1 - 5) indicating the relevance of the link and justfication to the POIs.


POI COLLECTION INSTRUCTIONS:

A Point of Interest (POI) must be a specific physical location that people can visit. When you find a POI, encode it as JSON:
{
   "current_url": "URL of the page",
   "name": "POI's official name",
   "location": "City/Area where POI is located",
   "category": "Type of POI (Beach, Temple, Museum, etc.)",
   "description": "Brief description of the POI"
}

Important Rules:
1. NEVER consider these as POIs:
  - Generic category names ("Tourist Spots in Chennai")
  - Section headings ("Places to Visit")
  - List titles ("Top 10 Attractions")

2. ONLY consider these as POIs:
  - Specific locations ("Marina Beach")
  - Named attractions ("Kapaleeshwarar Temple")
  - Actual venues ("Government Museum")

Examples:
Valid POIs:
{
   "current_url": "https://example.com",
   "name": "Marina Beach",
   "location": "Chennai",
   "category": "Beach",
   "description": "Marina Beach is a natural urban beach along the Bay of Bengal, stretching 6.0 km..."
}

{
   "current_url": "https://example.com",
   "name": "DakshinaChitra Museum",
   "location": "Muttukadu, Chennai",
   "category": "Museum",
   "description": "Living-history museum showcasing traditional South Indian crafts and architecture..."
}

Invalid POIs:
- "Popular Beaches in Chennai"
- "Heritage Sites to Explore"
- "Weekend Getaways"

If no specific POIs are found, return: "The page does not contain any POI information"

NEW LINK COLLECTION INSTRUCTIONS:

For each link found, you must:
1. Analyze the URL and context
2. Assign a score (1-5)
3. Call register_link function
4. Provide justification

Scoring Guide:

Score 5 (Definitely Contains POIs):
- /attractions/temples
- /tourist-spots/beaches
- /places-to-visit/museums
- /heritage-sites
Reason: Direct links to specific attractions or POI categories

Score 4 (Likely Contains POIs):
- /neighborhoods/t-nagar
- /shopping-districts
- /popular-areas
Reason: Areas that typically contain multiple POIs

Score 3 (Might Contain POIs):
- /tourism
- /city-guide
- /explore
Reason: General pages that could lead to POI information

Score 2 (Unlikely to Contain POIs):
- /how-to-reach
- /best-time-to-visit
- /travel-tips
Reason: Travel information without specific POIs

Score 1 (No POIs):
- /contact-us
- /about
- /privacy-policy
- /login
- /faq
- /terms-conditions
Reason: Administrative/utility pages

Example Link Registrations:

register_link(
   current_url="https://example.com",
   outgoing_url="https://example.com/attractions/temples",
   score=5,
   justification="Directory of temples, direct POI category"
)

register_link(
   current_url="https://example.com",
   outgoing_url="https://example.com/neighborhoods/mylapore",
   score=4,
   justification="Historic neighborhood with multiple attractions"
)

register_link(
   current_url="https://example.com",
   outgoing_url="https://example.com/city-guide",
   score=3,
   justification="General guide that might contain POI information"
)

register_link(
   current_url="https://example.com",
   outgoing_url="https://example.com/how-to-reach",
   score=2,
   justification="Travel information, unlikely to contain POIs"
)

register_link(
   current_url="https://example.com",
   outgoing_url="https://example.com/contact",
   score=1,
   justification="Contact page, no POI content expected"
)

FINAL MESSAGE:
- Once you have retrieved all the POI's from the webpage, all links with score and created the summary, you need to send the JSON-encoded summary to the web_surfer.
- You MUST not include any other text or formatting in the message, only JSON-encoded summary!

"""
            + f"""An example of the JSON-encoded summary:
{self.example_answer.model_dump_json()}

TERMINATION:
When YOU are finished and YOU have created JSON-encoded answer, write a single 'TERMINATE' to end the task.

OFTEN MISTAKES:
- Enclosing JSON-encoded answer in any other text or formatting including '```json' ... '```' or similar!
- Considering the category names like "Explore Chennai", "Things to do in Chennai", "Places to visit in Chennai" etc. as POIs. The POI's are the specific names like "Marina Beach", "Kapaleeshwarar Temple", "Arignar Anna Zoological Park" etc.
"""
        )

    @property
    def initial_message(self) -> str:
        return f"""We are tasked with the following task: {self.task}"""

    @property
    def error_message(self) -> str:
        return f"""Please output the JSON-encoded answer only in the following message before trying to terminate the chat.

IMPORTANT:
  - NEVER enclose JSON-encoded answer in any other text or formatting including '```json' ... '```' or similar!
  - NEVER write TERMINATE in the same message as the JSON-encoded answer!

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
            decision="CONTINUE",
            current_url="",
            description=f"unexpected error occurred: {e!s}",
        )

        return self.create_final_reply(task, answer)

    def create_final_reply(self, task: str, message: CustomWebSurferAnswer) -> str:
        retval = (
            "We have successfully completed the task:\n\n"
            if message.is_successful
            else "We have failed to complete the task:\n\n"
        )
        retval += f"{task}\n\n"
        retval += f"decision: {message.decision}\n"
        retval += f"current_url: {message.current_url}\n"
        retval += f"description: {message.description}\n\n"

        return retval

    @property
    def example_answer(self) -> CustomWebSurferAnswer:
        return CustomWebSurferAnswer.get_example_answer()
