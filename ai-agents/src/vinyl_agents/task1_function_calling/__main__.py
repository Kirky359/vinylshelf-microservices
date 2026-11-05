import asyncio

from vinyl_agents.task1_function_calling.app import FunctionCallingApplication

if __name__ == "__main__":  # python -m vinyl_agents.task1_function_calling
    asyncio.run(FunctionCallingApplication().run())
