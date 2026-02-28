from typing import List

from prefect.client.schemas import FlowRun

from workflow.schemas.workflow_run import WorkflowRun


def translate_flow_runs_schema(original_runs: List[FlowRun]) -> List[WorkflowRun]:
    """
    Takes a list of FlowRun objects and returns a list of slim WorkflowRun objects.
    """
    return [WorkflowRun.model_validate(run) for run in original_runs]
