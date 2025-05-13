# OpenG2P Unified Conversation Agent

[![Pre-commit Status](https://github.com/OpenG2P/openg2p-uca/actions/workflows/pre-commit.yml/badge.svg?branch=develop)](https://github.com/OpenG2P/openg2p-uca/actions/workflows/pre-commit.yml?query=branch%3Adevelop)
[![Build Status](https://github.com/OpenG2P/openg2p-uca/actions/workflows/test.yml/badge.svg?branch=develop)](https://github.com/OpenG2P/openg2p-uca/actions/workflows/test.yml?query=branch%3Adevelop)
[![codecov](https://codecov.io/gh/OpenG2P/openg2p-uca/branch/develop/graph/badge.svg)](https://codecov.io/gh/OpenG2P/openg2p-uca)
[![openapi](https://img.shields.io/badge/open--API-swagger-brightgreen)](https://validator.swagger.io/?url=https://raw.githubusercontent.com/OpenG2P/openg2p-uca/develop/api-docs/generated/openapi.json)

This is an exploration project to build an AI based Unified Conversation Agent (UCA) with a view to make the life of end users better and deliver useful services. UCA will leverate AI technologies to support OpenG2P use cases for social benefit delivery across programs and departments. This intelligent agent will engage directly with callers via voice, providing real-time updates on program statuses and disbursements, informing them about eligibility for additional programs, and enabling seamless program application entirely through phone or voice interactions.

## Developer Notes

### Running for development

- Create `.env`. TODO: expand.
- Create python virtual env and install python module.
  ```sh
  python3 -m venv .venv
  . .venv/bin/activate
  pip install -e ./openg2p-llm-common
  pip install -e ./openg2p-uca
  ```
- Run
  ```sh
  . .venv/bin/activate
  ./main.py run
  ```

## Licenses

This repository is licensed under [MPL-2.0](LICENSE).
