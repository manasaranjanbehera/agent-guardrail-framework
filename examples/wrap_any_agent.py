"""Shows GuardedAgent wrapping two different kinds of underlying agent:
a plain echo function, and (commented out) a real AWS Bedrock call
from the companion portfolio project. This is the point of the
design -- the guardrail layer doesn't care what's underneath.
"""
from src.audit_log import AuditLogger
from src.cost_tracker import CostTracker
from src.guardrail import GuardedAgent
from src.policy import PolicyEngine


def demo_with_plain_function():
    def my_agent(prompt: str) -> str:
        return f"[fake model reply to]: {prompt}"

    policy = PolicyEngine(denylist=["social security number", "wire transfer"])
    cost_tracker = CostTracker()
    cost_tracker.set_budget(actor="demo-user", usd=0.50)
    logger = AuditLogger(log_path="audit_log.jsonl")

    agent = GuardedAgent(call_fn=my_agent, policy=policy, cost_tracker=cost_tracker, audit_logger=logger)

    result = agent.invoke("Summarize today's tickets, my email is user@example.com", actor="demo-user")
    print("output:", result.output)
    print("estimated cost: $%.6f" % result.estimated_cost_usd)
    print("audit entries so far:", len(logger.entries))
    print("(raw email is NOT in the audit log — check audit_log.jsonl)")


# To wrap the real Bedrock research pipeline from
# ../01-agentic-research-assistant instead of the fake function above:
#
#   import sys; sys.path.insert(0, "../01-agentic-research-assistant")
#   from src.bedrock_client import BedrockChatClient
#   client = BedrockChatClient()
#   agent = GuardedAgent(call_fn=lambda p: client.run(system_prompt="You are helpful.", user_message=p))
#   agent.invoke("What is AWS Bedrock?", actor="demo-user")


if __name__ == "__main__":
    demo_with_plain_function()
