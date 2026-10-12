"""The editable guest entry point. The protected host never imports this file."""
from autoproteus.agent import Agent


def run(root, store, settings, client_factory, session, message=None):
    agent = Agent(root, store, settings, client_factory)
    agent.start(session, message)
    return agent
