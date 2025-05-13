FROM bitnami/python:3.10.13-debian-11-r24

ARG container_user=openg2p
ARG container_user_group=openg2p
ARG container_user_uid=1001
ARG container_user_gid=1001

RUN groupadd -g ${container_user_gid} ${container_user_group} \
  && useradd -N -u ${container_user_uid} -G ${container_user_group} -s /bin/bash ${container_user}

RUN install_packages libpq-dev \
  && apt-get clean && rm -rf /var/lib/apt/lists /var/cache/apt/archives

RUN python3 -m pip install git+https://github.com/openg2p/openg2p-fastapi-common@develop#subdirectory=openg2p-fastapi-common  # to_be_removed_on_tag
RUN python3 -m pip install git+https://github.com/openg2p/openg2p-fastapi-common@develop#subdirectory=openg2p-fastapi-auth  # to_be_removed_on_tag

ADD . /app

RUN python3 -m pip install -e /app/openg2p-llm-common
RUN python3 -m pip install -e /app/openg2p-uca

WORKDIR /app
USER ${container_user}

ENV UCA_NO_OF_WORKERS=1
ENV UCA_HOST=0.0.0.0
ENV UCA_PORT=8000
ENV UCA_WORKER_TYPE=gunicorn

CMD python3 main.py migrate; \
    gunicorn "main:app" --workers ${UCA_NO_OF_WORKERS} --worker-class uvicorn.workers.UvicornWorker --bind ${UCA_HOST}:${UCA_PORT}
