"""The Part 1 coding agent: fix a software issue and submit a git patch."""

from __future__ import annotations

import json
from typing import Any

from assignment.agent.base import (
    DEFAULT_COMPACTION_KEEP_RECENT_STEPS,
    DEFAULT_COMPACTION_MAX_TOKENS,
    Agent,
    format_tool_output
)


from assignment.agent.tools import EXECUTE_TOOL, SEND_MESSAGE_TOOL
from assignment.env import Environment

class CodeAgent(Agent):
    """An agent that fixes a software issue and submits a git patch."""

    def __init__(
        self,
        task: str,
        environment: Environment,
        model: str | None = None,
        logs_save_path: str | None = None,
        step_limit: int = 100,
        skills_path: str | None = None,
        auto_stop_environment: bool = True,
        compact_threshold_tokens: int | None = None,
        compaction_keep_recent_steps: int = DEFAULT_COMPACTION_KEEP_RECENT_STEPS,
        compaction_max_tokens: int = DEFAULT_COMPACTION_MAX_TOKENS,
    ):
        super().__init__(
            environment=environment,
            model=model,
            logs_save_path=logs_save_path,
            step_limit=step_limit,
            skills_path=skills_path,
            auto_stop_environment=auto_stop_environment,
            compact_threshold_tokens=compact_threshold_tokens,
            compaction_keep_recent_steps=compaction_keep_recent_steps,
            compaction_max_tokens=compaction_max_tokens,
        )
        self.task = task
        self.submitted_patch = ""

        # TODO(Part 1.3): Make the `execute` and `send_message` tools available
        # to the agent.
        self.tools.extend([EXECUTE_TOOL, SEND_MESSAGE_TOOL])


        # TODO(1.1.b): Construct the system prompt and task_prompt. These
        # should be usable by the `Agent.build_prompt` method.
        # Extend rather than replace: Agent may already expose invoke_skill.
        # Extend rather than replace: Agent may already expose invoke_skill.
        
        system_information = {
            key: getattr(self.env, key)
            for key in ("machine", "release", "system", "version")
        }

        self.system_prompt = (
            "You are a coding agent working in a terminal sandbox. "
            "Investigate the reported issue, make focused source changes, "
            "and run relevant tests. Use the available tools to act on "
            "the task. Inspect tool results and adjust your approach "
            "when commands fail.\n\n"
            "<system_information>\n"
            + json.dumps(system_information, indent=2)
            + "\n</system_information>"
        )
        self.task_prompt = self.task
        
        # TODO(1.4): If any skills are available to the agent, make their
        # descriptions/metadata available to the agent in the prompt.
        if self.skills:
            catalog = "\n\n".join(
                skill["metadata"] for skill in self.skills.values()
            )
            self.system_prompt += (
                "\n\nAvailable skills:\n"
                + catalog
                + "\nUse invoke_skill to read a relevant skill "
                  "before following its workflow."
            )

        self.task_prompt = self.task
    def execute_tool_calls(
        self, tool_calls: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        """Execute ``execute`` and ``send_message`` calls in the code sandbox."""
    
        # TODO(Part 1.3): Parse each call, execute recognized tools, and return
        # one message per call (there may be multiple tool calls in one agent
        # response!). Malformed JSON and unknown tools must become recoverable
        # observations relayed to the agent instead of exceptions.
        observations: list[dict[str, str]] = []

        for call in tool_calls:
            call_id = call.get("id", "")

            try:
                if self.finished:
                    raise ValueError("The task has already been submitted.")

                function = call["function"]
                name = function["name"]
                arguments = json.loads(function["arguments"])

                if not isinstance(arguments, dict):
                    raise ValueError("Tool arguments must be a JSON object.")

                # Execute terminal commands inside the sandbox.
                if name == "execute":
                    allowed = {"command", "timeout", "cwd", "env", "shell"}
                    if set(arguments) - allowed:
                        raise ValueError("Unexpected execute arguments.")

                    command = arguments.get("command")
                    valid_command = isinstance(command, str) or (
                        isinstance(command, list)
                        and bool(command)
                        and all(isinstance(arg, str) for arg in command)
                    )
                    if not valid_command:
                        raise ValueError(
                            "command must be a string or a nonempty "
                            "list of strings."
                        )

                    result = self.env.execute(**arguments)
                    content = format_tool_output(result)

                # Return a skill's full instructions when requested.
                elif name == "invoke_skill":
                    if (
                        set(arguments) != {"name"}
                        or not isinstance(arguments["name"], str)
                    ):
                        raise ValueError("invoke_skill requires a string name.")

                    skill_name = arguments["name"]
                    if skill_name not in self.skills:
                        raise ValueError(f"Unknown skill: {skill_name}")

                    content = self.skills[skill_name]["content"]

                # Capture the patch and finish the task on final submission.
                elif name == "send_message":
                    if (
                        set(arguments) != {"summary"}
                        or not isinstance(arguments["summary"], str)
                    ):
                        raise ValueError(
                            "send_message requires a string summary."
                        )

                    # Capture the full artifact before the sandbox is stopped.
                    result = self.env.execute("cat patch.txt")
                    if (
                        result.get("returncode") != 0
                        or result.get("exception_info")
                    ):
                        raise ValueError(
                            "Cannot read the submission artifact: "
                            + format_tool_output(result)
                        )

                    patch = result.get("output", "")
                    if not isinstance(patch, str) or not patch.strip():
                        raise ValueError("The submission artifact is empty.")

                    self.submitted_patch = patch
                    self.finished = True
                    print(arguments["summary"], flush=True)
                    content = "Submission received."

                else:
                    raise ValueError(f"Unknown tool: {name}")

            # Convert failures into observations so the agent can recover.
            except (ValueError, TypeError, KeyError) as exc:
                content = f"<error>{type(exc).__name__}: {exc}</error>"

       

            # Link this observation to the model's original tool call.
            observations.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": name,  # Actual function name: execute, invoke_skill, etc.
                    "content": content,
                }
            )

        return observations
    
    #raise NotImplementedError
