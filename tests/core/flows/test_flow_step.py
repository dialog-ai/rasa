from typing import Type

import pytest

from rasa.shared.core.flows import Flow, FlowStep
from rasa.shared.core.flows.steps import (
    ActionFlowStep,
    CollectInformationFlowStep,
    GenerateResponseFlowStep,
    LinkFlowStep,
    SetSlotsFlowStep,
)
from rasa.shared.core.flows.yaml_flows_io import flows_from_str


@pytest.fixture
def flow_with_all_steps() -> Flow:
    flows = flows_from_str(
        """
            flows:
              test_flow:
                steps:
                  - id: action_step
                    action: utter_greet
                  - id: set_slots_step
                    set_slots:
                      - has_been_greeted: True
                      - will_be_interesting: unsure
                  - id: collect_step
                    collect: topic
                    ask_before_filling: True
                    reset_after_flow_ends: False
                    rejections:
                      - if: "topic != large language models"
                        utter: utter_too_boring
                  - id: flow_step
                    next: generation_step
                  - id: generation_step
                    generation_prompt: "Engage the user on the chosen topic:"
                    llm:
                      model: "gpt-5"
                  - id: link_step
                    link: test_flow
                  """
    )
    return flows.flow_by_id("test_flow")


@pytest.mark.parametrize(
    "flow_step_id, flow_step_class",
    [
        ("action_step", ActionFlowStep),
        ("set_slots_step", SetSlotsFlowStep),
        ("collect_step", CollectInformationFlowStep),
        ("flow_step", FlowStep),
        ("generation_step", GenerateResponseFlowStep),
        ("link_step", LinkFlowStep),
    ],
)
def test_flow_step_serialization(
    flow_step_id: str, flow_step_class: Type[FlowStep], flow_with_all_steps: Flow
):
    """Testing for all flow steps that serialization does not add or remove data."""
    step = flow_with_all_steps.step_by_id(flow_step_id)
    # using exact type check because FlowStep, the superclass, is also one of
    # the classes tested
    assert type(step) is flow_step_class
    step_data = step.as_json()
    step_from_data = flow_step_class.from_json(step_data)
    # overwriting idx of the re-serialized class as this is normally only happening
    # when reading entire flows
    step_from_data.idx = step.idx
    assert step == step_from_data


def test_action_flow_step_attributes(flow_with_all_steps: Flow):
    step = flow_with_all_steps.step_by_id("action_step")
    assert isinstance(step, ActionFlowStep)
    assert step.action == "utter_greet"


def test_set_slots_flow_step_attributes(flow_with_all_steps: Flow):
    step = flow_with_all_steps.step_by_id("set_slots_step")
    assert isinstance(step, SetSlotsFlowStep)
    assert len(step.slots) == 2
    assert step.slots[0]["key"] == "has_been_greeted"
    assert step.slots[0]["value"]
    assert step.slots[1]["key"] == "will_be_interesting"
    assert step.slots[1]["value"] == "unsure"


def test_collect_flow_step_attributes(flow_with_all_steps: Flow):
    step = flow_with_all_steps.step_by_id("collect_step")
    assert isinstance(step, CollectInformationFlowStep)
    assert step.collect == "topic"
    assert step.ask_before_filling
    assert not step.reset_after_flow_ends
    assert len(step.rejections) == 1
    assert step.rejections[0].utter == "utter_too_boring"


def test_flow_step_attributes(flow_with_all_steps: Flow):
    step = flow_with_all_steps.step_by_id("flow_step")
    assert type(step) is FlowStep
    assert len(step.next.links) == 1
    assert step.next.links[0].target == "generation_step"


def test_generation_step_attributes(flow_with_all_steps: Flow):
    step = flow_with_all_steps.step_by_id("generation_step")
    assert isinstance(step, GenerateResponseFlowStep)
    assert step.generation_prompt.startswith("Engage")
    assert step.llm_config["model"] == "gpt-5"


def test_link_step_attributes(flow_with_all_steps: Flow):
    step = flow_with_all_steps.step_by_id("link_step")
    assert isinstance(step, LinkFlowStep)
    assert step.link == "test_flow"
