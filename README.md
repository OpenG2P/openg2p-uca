# OpenG2P Unified Conversation Agent

[![Pre-commit Status](https://github.com/OpenG2P/openg2p-uca/actions/workflows/pre-commit.yml/badge.svg?branch=develop)](https://github.com/OpenG2P/openg2p-uca/actions/workflows/pre-commit.yml?query=branch%3Adevelop)
[![Build Status](https://github.com/OpenG2P/openg2p-uca/actions/workflows/test.yml/badge.svg?branch=develop)](https://github.com/OpenG2P/openg2p-uca/actions/workflows/test.yml?query=branch%3Adevelop)
[![codecov](https://codecov.io/gh/OpenG2P/openg2p-uca/branch/develop/graph/badge.svg)](https://codecov.io/gh/OpenG2P/openg2p-uca)
[![openapi](https://img.shields.io/badge/open--API-swagger-brightgreen)](https://validator.swagger.io/?url=https://raw.githubusercontent.com/OpenG2P/openg2p-uca/develop/api-docs/generated/openapi.json)

This is an exploration project to build an AI based Unified Conversation Agent (UCA) with a view to make the life of end users better and deliver useful services. UCA will leverate AI technologies to support OpenG2P use cases for social benefit delivery across programs and departments. This intelligent agent will engage directly with callers via voice, providing real-time updates on program statuses and disbursements, informing them about eligibility for additional programs, and enabling seamless program application entirely through phone or voice interactions.

## Developer Notes

### Prerequisites

[Ollama](https://ollama.com/download), [docker](https://docs.docker.com/engine/install/) are installed on the machine which contains GPU.

- Note: Add `OLLAMA_HOST=0.0.0.0` env var in ollama startup command.

### Running using Docker

- Create `.env` file from [sample env file](./.env.sample).
- Edit the `.env` file with appropriate values.
  - If using Windows/MacOS, replace `172.17.0.1` with `host.docker.internal` in `.env` file.
- Start services.
  ```sh
  docker compose up -d
  ```

### Running for development

- Create `.env` file and edit it, same as the above section.
  - Change API_BACKEND_URL ENV var to `API_BACKEND_URL=http://172.17.0.1:8000/` for Linux. Or `API_BACKEND_URL=http://host.docker.internal:8000/` for Windows/MacOS.
- Start opensearch and UI.
  ```sh
  docker compose up -d opensearch-dashboards
  docker compose up -d ui
  ```
- Create python virtual env and install python module.
  ```sh
  python3 -m venv .venv
  . .venv/bin/activate
  pip install -e ./openg2p-llm-common
  pip install -e ./openg2p-uca
  ```
- If you want calling and voice message (speech-to-text and text-to-speech aspects), run:
  ```
  pip install "./openg2p-llm-common[stt-vosk,tts-orpheus]"
  pip install "./openg2p-uca[stt-vosk,tts-orpheus]"
  ```
- Run
  ```sh
  . .venv/bin/activate
  ./main.py migrate && ./main.py run
  ```
- UCA APIs should be accessible at http://localhost:8001/v1/uca/docs. UCA UI should be accessible at http://localhost:8001/chat.

## Licenses

This repository is licensed under [MPL-2.0](LICENSE).
