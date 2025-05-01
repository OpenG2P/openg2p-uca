FROM bitnami/python:3.10.13-debian-11-r24

ARG container_user=openg2p
ARG container_user_group=openg2p
ARG container_user_uid=1001
ARG container_user_gid=1001

RUN groupadd -g ${container_user_gid} ${container_user_group} \
  && useradd -N -u ${container_user_uid} -G ${container_user_group} -s /bin/bash ${container_user}

RUN install_packages libpq-dev libmagic-dev wkhtmltopdf \
  && apt-get clean && rm -rf /var/lib/apt/lists /var/cache/apt/archives

RUN python3 -m pip install git+https://github.com/openg2p/openg2p-fastapi-common@develop#subdirectory=openg2p-fastapi-common

ADD . /app

RUN python3 -m pip install -e /app

WORKDIR /app
USER ${container_user}

ENTRYPOINT [ "bash" ]
CMD ["-c" , "exec python3 main.py run"]
