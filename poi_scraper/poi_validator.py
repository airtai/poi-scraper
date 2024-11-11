from dataclasses import dataclass
from typing import Any, Optional, Union

from autogen import AssistantAgent, UserProxyAgent
from fastagency import UI


@dataclass
class PoiValidationResult:
    """A class to represent the result of a POI (Point of Interest) validation.

    Attributes:
        is_valid (bool): Indicates whether the POI is valid.
        name (str): The name of the POI.
        description (str): The description of the POI.
        raw_response (str): The raw response from the validation process.
    """

    is_valid: bool
    name: str
    description: str
    raw_response: str


class PoiDataBase:
    """Class for storing the Points of Interest (POI)."""

    SYSTEM_MESSAGE = """You are a helpful agent. Your task is to determine if a given name qualifies as a Point of Interest (POI).

    Definition of a POI:
        A POI is a specific place where people can visit or gather, such as tourist attractions, landmarks, parks, museums, cultural venues, and historic sites.
        General terms that describe activities or broad categories, like "Things to do in Chennai" or "Places to visit in Chennai," are not POIs.

    Instructions:
        If the given name is a POI, reply with "Yes".
        If the given name is not a POI, reply with "No".
        Do not provide any response other than "Yes" or "No"; you will be penalized for any additional information.

    Examples:
        - name: "Marina Beach", description: "Marina Beach is a natural urban beach in Chennai, Tamil Nadu, India."
        - Your response: "Yes"

        - name: "Explore Chennai", description: "Discover the best places to visit in Chennai."
        - Your response: "No"

        - name: "Kapaleeshwarar Temple", description: "Kapaleeshwarar Temple is a Hindu temple dedicated to Lord Shiva."
        - Your response: "Yes"

        - name: "Best Restaurants in Chennai", description: "Explore the top restaurants in Chennai."
        - Your response: "No"

        - name: "Arignar Anna Zoological Park", description: "Arignar Anna Zoological Park is a zoological garden located in Vandalur, a suburb in the southwestern part of Chennai."
        - Your response: "Yes"

        - name: "Treks in Chennai", description: "Discover the best trekking spots in Chennai."
        - Your response: "No"
"""

    def __init__(self, llm_config: dict[str, Any], ui: UI):
        """Initialize POI validator with optional custom configuration

        Args:
            agent_config: Optional custom configuration for the validator agent
        """
        self.llm_config = llm_config
        self.ui = ui
        self._validator_agent = None
        self._user_proxy = None
        self.registered_pois: dict[str, dict[str, Union[str, Optional[str]]]] = {}
        self.un_registered_pois: dict[str, dict[str, Union[str, Optional[str]]]] = {}

    @property
    def validator_agent(self) -> AssistantAgent:
        """Lazy initialization of validator agent."""
        if self._validator_agent is None:
            self._validator_agent = AssistantAgent(
                name="POI_Validator_Agent",
                system_message=PoiDataBase.SYSTEM_MESSAGE,
                llm_config=self.llm_config,
                human_input_mode="NEVER",
            )
        return self._validator_agent

    @property
    def user_proxy(self) -> UserProxyAgent:
        """Lazy initialization of user proxy agent."""
        if self._user_proxy is None:
            self._user_proxy = UserProxyAgent(
                name="Poi_User_Proxy_Agent",
                system_message="You are a helpful agent",
                llm_config=self.llm_config,
            )
        return self._user_proxy

    def register(
        self, name: str, description: str, category: str, location: Optional[str]
    ) -> str:
        initial_message = f"""Please confirm if the below is a Point of Interest (POI).

- name:  {name}
- description: {description}
"""
        chat_result = self.user_proxy.initiate_chat(
            self.validator_agent,
            message=initial_message,
            summary_method="reflection_with_llm",
            max_turns=1,
        )

        messages = [msg["content"] for msg in chat_result.chat_history]
        last_message = messages[-1]

        result = PoiValidationResult(
            is_valid=last_message.lower() == "yes",
            name=name,
            description=description,
            raw_response=last_message,
        )

        if result.is_valid:
            self.registered_pois[name] = {
                "description": description,
                "category": category,
                "location": location,
            }
            self.ui.text_message(
                sender="WebSurfer",
                recipient="POI Database",
                body=f"POI registered. name: {name}, description: {description}, category: {category}, location: {location}",
            )
            return "POI registered"
        else:
            self.un_registered_pois[name] = {
                "description": description,
                "category": category,
                "location": location,
            }

        self.ui.text_message(
            sender="WebSurfer",
            recipient="POI Database",
            body=f"POI not registered. name: {name}, description: {description}, category: {category}, location: {location}",
        )
        return "POI not registered"
