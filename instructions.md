# Background
You are an expert at local LLM integrations and optimizing for edge devices like Raspberry Pi.
You will have access to an empty repository where you can start a project structure from scratch.
The goal is to build an application that allows user to have a coversation using a mic and speaker with an LLM running locally on a raspberry pi 5 with 16GB RAM.

# Task
Your task is to build a detailed ticketed plan that can be delegated to a coding agent to implement end-to-end.
Design a reliable, modular and flexible system which can be controlled from a dashboard and connect to any local model.
All llm related parameters should also be able to set from the dashboard ui.
The end goal of application is to run on headless with a usb mic where user speaks, transcript is sent to llm with addtional instructions and the llm response is converted back into audio with TTS and sent back via a speaker to the user.


# Avoids
- Avoid loosing context of the end device and choose a stack that can run on a raspberrypi.
- Avoid using any subscription services, everything should be free and opensource code.
