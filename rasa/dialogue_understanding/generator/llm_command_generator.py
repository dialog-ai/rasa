import importlib.resources
import re
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple, Union

import structlog
from jinja2 import Template

from rasa.dialogue_understanding.commands import (
    Command,
    ErrorCommand,
    SetSlotCommand,
    CancelFlowCommand,
    StartFlowCommand,
    HumanHandoffCommand,
    ChitChatAnswerCommand,
    SkipQuestionCommand,
    KnowledgeAnswerCommand,
    ClarifyCommand,
)
from rasa.dialogue_understanding.generator import CommandGenerator
from rasa.dialogue_understanding.stack.utils import top_flow_frame
from rasa.engine.graph import GraphComponent, ExecutionContext
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage
from rasa.shared.constants import (
    RASA_PATTERN_INTERNAL_ERROR_USER_INPUT_TOO_LONG,
    RASA_PATTERN_INTERNAL_ERROR_USER_INPUT_EMPTY,
)
from rasa.shared.core.flows import FlowStep, Flow, FlowsList
from rasa.shared.core.flows.steps.collect import CollectInformationFlowStep
from rasa.shared.core.slots import (
    BooleanSlot,
    CategoricalSlot,
    Slot,
)
from rasa.shared.core.trackers import DialogueStateTracker
from rasa.shared.nlu.constants import TEXT
from rasa.shared.nlu.training_data.message import Message
from rasa.shared.nlu.training_data.training_data import TrainingData
from rasa.shared.utils.llm import (
    DEFAULT_OPENAI_CHAT_MODEL_NAME_ADVANCED,
    DEFAULT_OPENAI_MAX_GENERATED_TOKENS,
    get_prompt_template,
    llm_factory,
    tracker_as_readable_transcript,
    sanitize_message_for_prompt,
    DEFAULT_MAX_USER_INPUT_CHARACTERS,
)


DEFAULT_COMMAND_PROMPT_TEMPLATE = importlib.resources.read_text(
    "rasa.dialogue_understanding.generator", "command_prompt_template.jinja2"
)

DEFAULT_LLM_CONFIG = {
    "_type": "openai",
    "request_timeout": 7,
    "temperature": 0.0,
    "model_name": DEFAULT_OPENAI_CHAT_MODEL_NAME_ADVANCED,
    "max_tokens": DEFAULT_OPENAI_MAX_GENERATED_TOKENS,
}

LLM_CONFIG_KEY = "llm"
USER_INPUT_CONFIG_KEY = "user_input"

structlogger = structlog.get_logger()


@dataclass
class UserInputConfig:
    """Configuration class for user input settings."""

    max_characters: int = DEFAULT_MAX_USER_INPUT_CHARACTERS
    """The maximum number of characters allowed in the user input."""

    def __post_init__(self) -> None:
        if self.max_characters is None:
            self.max_characters = DEFAULT_MAX_USER_INPUT_CHARACTERS

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserInputConfig":
        return cls(
            max_characters=data.get("max_characters", DEFAULT_MAX_USER_INPUT_CHARACTERS)
        )


@DefaultV1Recipe.register(
    [
        DefaultV1Recipe.ComponentType.COMMAND_GENERATOR,
    ],
    is_trainable=True,
)
class LLMCommandGenerator(GraphComponent, CommandGenerator):
    """An LLM-based command generator."""

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """The component's default config (see parent class for full docstring)."""
        return {
            "prompt": None,
            USER_INPUT_CONFIG_KEY: None,
            LLM_CONFIG_KEY: None,
        }

    def __init__(
        self,
        config: Dict[str, Any],
        model_storage: ModelStorage,
        resource: Resource,
    ) -> None:
        self.config = {**self.get_default_config(), **config}
        self.prompt_template = get_prompt_template(
            config.get("prompt"),
            DEFAULT_COMMAND_PROMPT_TEMPLATE,
        )
        self.user_input_config = UserInputConfig.from_dict(
            config.get("user_input") or {}
        )
        self._model_storage = model_storage
        self._resource = resource

    @classmethod
    def create(
        cls,
        config: Dict[str, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
    ) -> "LLMCommandGenerator":
        """Creates a new untrained component (see parent class for full docstring)."""
        return cls(config, model_storage, resource)

    @classmethod
    def load(
        cls,
        config: Dict[str, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
        **kwargs: Any,
    ) -> "LLMCommandGenerator":
        """Loads trained component (see parent class for full docstring)."""
        return cls(config, model_storage, resource)

    def persist(self) -> None:
        pass

    def train(self, training_data: TrainingData) -> Resource:
        """Train the intent classifier on a data set."""
        self.persist()
        return self._resource

    def predict_commands(
        self,
        message: Message,
        flows: FlowsList,
        tracker: Optional[DialogueStateTracker] = None,
    ) -> List[Command]:
        """Predict commands using the LLM.

        Args:
            message: The message from the user.
            flows: The flows available to the user.
            tracker: The tracker containing the current state of the conversation.

        Returns:
            The commands generated by the llm.
        """
        if tracker is None or flows.is_empty():
            # cannot do anything if there are no flows or no tracker
            return []
        if self.check_if_message_is_empty(message):
            return [
                ErrorCommand(error_type=RASA_PATTERN_INTERNAL_ERROR_USER_INPUT_EMPTY)
            ]
        if self.check_if_message_exceeds_limit(message):
            # notify the user about message length
            return [
                ErrorCommand(
                    error_type=RASA_PATTERN_INTERNAL_ERROR_USER_INPUT_TOO_LONG,
                    info={"max_characters": self.user_input_config.max_characters},
                )
            ]

        flow_prompt = self.render_template(message, tracker, flows)
        structlogger.info(
            "llm_command_generator.predict_commands.prompt_rendered", prompt=flow_prompt
        )
        action_list = self._generate_action_list_using_llm(flow_prompt)
        structlogger.info(
            "llm_command_generator.predict_commands.actions_generated",
            action_list=action_list,
        )
        commands = self.parse_commands(action_list, tracker)
        structlogger.info(
            "llm_command_generator.predict_commands.finished",
            commands=commands,
        )

        return commands

    def render_template(
        self, message: Message, tracker: DialogueStateTracker, flows: FlowsList
    ) -> str:
        """Render the jinja template to create the prompt for the LLM.

        Args:
            message: The current message from the user.
            tracker: The tracker containing the current state of the conversation.
            flows: The flows available to the user.

        Returns:
            The rendered prompt template.
        """
        top_relevant_frame = top_flow_frame(tracker.stack)
        top_flow = top_relevant_frame.flow(flows) if top_relevant_frame else None
        current_step = top_relevant_frame.step(flows) if top_relevant_frame else None

        flow_slots = self.prepare_current_flow_slots_for_template(
            top_flow, current_step, tracker
        )
        current_slot, current_slot_description = self.prepare_current_slot_for_template(
            current_step
        )
        current_conversation = tracker_as_readable_transcript(tracker)
        latest_user_message = sanitize_message_for_prompt(message.get(TEXT))
        current_conversation += f"\nUSER: {latest_user_message}"

        inputs = {
            "available_flows": self.prepare_flows_for_template(flows, tracker),
            "current_conversation": current_conversation,
            "flow_slots": flow_slots,
            "current_flow": top_flow.id if top_flow is not None else None,
            "current_slot": current_slot,
            "current_slot_description": current_slot_description,
            "user_message": latest_user_message,
        }

        return Template(self.prompt_template).render(**inputs)

    def _generate_action_list_using_llm(self, prompt: str) -> Optional[str]:
        """Use LLM to generate a response.

        Args:
            prompt: The prompt to send to the LLM.

        Returns:
            The generated text.
        """
        llm = llm_factory(self.config.get(LLM_CONFIG_KEY), DEFAULT_LLM_CONFIG)

        try:
            return llm(prompt)
        except Exception as e:
            # unfortunately, langchain does not wrap LLM exceptions which means
            # we have to catch all exceptions here
            structlogger.error("llm_command_generator.llm.error", error=e)
            return None

    @classmethod
    def parse_commands(
        cls, actions: Optional[str], tracker: DialogueStateTracker
    ) -> List[Command]:
        """Parse the actions returned by the llm into intent and entities.

        Args:
            actions: The actions returned by the llm.
            tracker: The tracker containing the current state of the conversation.

        Returns:
            The parsed commands.
        """
        if not actions:
            return [ErrorCommand()]

        commands: List[Command] = []

        slot_set_re = re.compile(
            r"""SetSlot\(([a-zA-Z_][a-zA-Z0-9_-]*?), ?\"?([^)]*?)\"?\)"""
        )
        start_flow_re = re.compile(r"StartFlow\(([a-zA-Z_][a-zA-Z0-9_-]*?)\)")
        cancel_flow_re = re.compile(r"CancelFlow\(\)")
        chitchat_re = re.compile(r"ChitChat\(\)")
        skip_question_re = re.compile(r"SkipQuestion\(\)")
        knowledge_re = re.compile(r"SearchAndReply\(\)")
        humand_handoff_re = re.compile(r"HumanHandoff\(\)")
        clarify_re = re.compile(r"Clarify\(([a-zA-Z0-9_, ]+)\)")

        for action in actions.strip().splitlines():
            if match := slot_set_re.search(action):
                slot_name = match.group(1).strip()
                slot_value = cls.clean_extracted_value(match.group(2))
                # error case where the llm tries to start a flow using a slot set
                if slot_name == "flow_name":
                    commands.append(StartFlowCommand(flow=slot_value))
                else:
                    typed_slot_value = cls.get_nullable_slot_value(slot_value)
                    commands.append(
                        SetSlotCommand(name=slot_name, value=typed_slot_value)
                    )
            elif match := start_flow_re.search(action):
                commands.append(StartFlowCommand(flow=match.group(1).strip()))
            elif cancel_flow_re.search(action):
                commands.append(CancelFlowCommand())
            elif chitchat_re.search(action):
                commands.append(ChitChatAnswerCommand())
            elif skip_question_re.search(action):
                commands.append(SkipQuestionCommand())
            elif knowledge_re.search(action):
                commands.append(KnowledgeAnswerCommand())
            elif humand_handoff_re.search(action):
                commands.append(HumanHandoffCommand())
            elif match := clarify_re.search(action):
                options = [opt.strip() for opt in match.group(1).split(",")]
                commands.append(ClarifyCommand(options))

        return commands

    @staticmethod
    def is_none_value(value: str) -> bool:
        """Check if the value is a none value."""
        return value in {
            "[missing information]",
            "[missing]",
            "None",
            "undefined",
            "null",
        }

    @staticmethod
    def clean_extracted_value(value: str) -> str:
        """Clean up the extracted value from the llm."""
        # replace any combination of single quotes, double quotes, and spaces
        # from the beginning and end of the string
        return value.strip("'\" ")

    @classmethod
    def get_nullable_slot_value(cls, slot_value: str) -> Union[str, None]:
        """Get the slot value or None if the value is a none value.

        Args:
            slot_value: the value to coerce

        Returns:
            The slot value or None if the value is a none value.
        """
        return slot_value if not cls.is_none_value(slot_value) else None

    def prepare_flows_for_template(
        self, flows: FlowsList, tracker: DialogueStateTracker
    ) -> List[Dict[str, Any]]:
        """Format data on available flows for insertion into the prompt template.

        Args:
            flows: The flows available to the user.
            tracker: The tracker containing the current state of the conversation.

        Returns:
            The inputs for the prompt template.
        """
        result = []
        for flow in flows.user_flows:
            slots_with_info = [
                {
                    "name": q.collect,
                    "description": q.description,
                    "allowed_values": self.allowed_values_for_slot(
                        tracker.slots[q.collect]
                    ),
                }
                for q in flow.get_collect_steps()
                if self.is_extractable(q, tracker)
            ]
            result.append(
                {
                    "name": flow.id,
                    "description": flow.description,
                    "slots": slots_with_info,
                }
            )
        return result

    @staticmethod
    def is_extractable(
        collect_step: CollectInformationFlowStep,
        tracker: DialogueStateTracker,
        current_step: Optional[FlowStep] = None,
    ) -> bool:
        """Check if the `collect` can be filled.

        A collect slot can only be filled if the slot exist
        and either the collect has been asked already or the
        slot has been filled already.

        Args:
            collect_step: The collect_information step.
            tracker: The tracker containing the current state of the conversation.
            current_step: The current step in the flow.

        Returns:
            `True` if the slot can be filled, `False` otherwise.
        """
        slot = tracker.slots.get(collect_step.collect)
        if slot is None:
            return False

        return (
            # we can fill because this is a slot that can be filled ahead of time
            not collect_step.ask_before_filling
            # we can fill because the slot has been filled already
            or slot.has_been_set
            # we can fill because the is currently getting asked
            or (
                current_step is not None
                and isinstance(current_step, CollectInformationFlowStep)
                and current_step.collect == collect_step.collect
            )
        )

    def allowed_values_for_slot(self, slot: Slot) -> Union[str, None]:
        """Get the allowed values for a slot."""
        if isinstance(slot, BooleanSlot):
            return str([True, False])
        if isinstance(slot, CategoricalSlot):
            return str([v for v in slot.values if v != "__other__"])
        else:
            return None

    @staticmethod
    def get_slot_value(tracker: DialogueStateTracker, slot_name: str) -> str:
        """Get the slot value from the tracker.

        Args:
            tracker: The tracker containing the current state of the conversation.
            slot_name: The name of the slot.

        Returns:
            The slot value as a string.
        """
        slot_value = tracker.get_slot(slot_name)
        if slot_value is None:
            return "undefined"
        else:
            return str(slot_value)

    def prepare_current_flow_slots_for_template(
        self, top_flow: Flow, current_step: FlowStep, tracker: DialogueStateTracker
    ) -> List[Dict[str, Any]]:
        """Prepare the current flow slots for the template.

        Args:
            top_flow: The top flow.
            current_step: The current step in the flow.
            tracker: The tracker containing the current state of the conversation.

        Returns:
            The slots with values, types, allowed values and a description.
        """
        if top_flow is not None:
            flow_slots = [
                {
                    "name": collect_step.collect,
                    "value": self.get_slot_value(tracker, collect_step.collect),
                    "type": tracker.slots[collect_step.collect].type_name,
                    "allowed_values": self.allowed_values_for_slot(
                        tracker.slots[collect_step.collect]
                    ),
                    "description": collect_step.description,
                }
                for collect_step in top_flow.get_collect_steps()
                if self.is_extractable(collect_step, tracker, current_step)
            ]
        else:
            flow_slots = []
        return flow_slots

    def prepare_current_slot_for_template(
        self, current_step: FlowStep
    ) -> Tuple[Union[str, None], Union[str, None]]:
        """Prepare the current slot for the template."""
        return (
            (current_step.collect, current_step.description)
            if isinstance(current_step, CollectInformationFlowStep)
            else (None, None)
        )

    def check_if_message_exceeds_limit(self, message: Message) -> bool:
        """Checks if the given message exceeds the predefined number of characters."""
        # if limit was a negative number, omit it
        if self.user_input_config.max_characters < 0:
            return False
        return len(message.get(TEXT, "")) > self.user_input_config.max_characters

    def check_if_message_is_empty(self, message: Message) -> bool:
        return len(message.get(TEXT, "").strip()) == 0
